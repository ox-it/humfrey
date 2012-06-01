import collections
import copy
import functools
import itertools
import logging

from celery.task import task
import ckanclient
from django.conf import settings
from django_hosts.reverse import reverse_full
import rdflib

from humfrey.sparql.endpoint import Endpoint
from humfrey.utils.namespaces import NS, HUMFREY, expand

from humfrey.linkeddata.resource import Resource
from humfrey.linkeddata.uri import doc_forward

logger = logging.getLogger(__name__)

DEFAULT_STORE_NAME = getattr(settings, 'DEFAULT_STORE_NAME', 'public')

_dataset_query = """
    DESCRIBE ?dataset ?publisher ?contact WHERE {
      GRAPH ?graph {
        ?dataset a void:Dataset
      } .
      OPTIONAL { ?dataset oo:contact ?contact } .
      OPTIONAL { ?dataset dcterms:publisher ?publisher } .
    }
    BINDINGS ?graph {
      %s
    }
"""

_licenses = {
    'http://creativecommons.org/publicdomain/zero/1.0/': 'cc-zero',
    'http://opendatacommons.org/licenses/pddl/1.0/': 'odc-pddl',
    'http://opendatacommons.org/licenses/odbl/1.0/': 'odc-odbl',
    'http://creativecommons.org/licenses/by/1.0/': 'cc-by',
    'http://creativecommons.org/licenses/by/2.0/': 'cc-by',
    'http://creativecommons.org/licenses/by/2.5/': 'cc-by',
    'http://creativecommons.org/licenses/by/3.0/': 'cc-by',
    'http://creativecommons.org/licenses/by-sa/2.0/': 'cc-by-sa',
    'http://www.nationalarchives.gov.uk/doc/open-government-licence/': 'uk-ogl',
}

# TODO: Picking local language
def _find_inner(graph, subject, predicates, datatypes=None, all=False):
    coerce = lambda o: unicode(o) if isinstance(o, rdflib.Literal) else o
    objects = set()
    for predicate in predicates:
        if predicate.startswith('^'):
            objects |= set(graph.subjects(expand(predicate[1:]), subject))
        else:
            objects |= set(graph.objects(subject, expand(predicate)))
    objects = list(objects)
    if datatypes:
        for datatype in datatypes:
            found = [o for o in objects if isinstance(o, rdflib.Literal) and o.datatype == datatype]
            if found and all:
                return map(coerce, found)
            elif found:
                return coerce(found[0])
        else:
            if all:
                return []
    elif all:
        return map(coerce, objects)
    elif objects:
        return coerce(objects[0])

def _find(graph, subject, path, datatypes=None, all=False):
    if datatypes and not isinstance(datatypes, tuple):
        datatypes = (datatypes,)
    if not path:
        return subject

    path = path.split('/')
    objects = set([subject])
    for predicates in path:
        predicates = predicates.split('|')
        objects = set(itertools.chain(*(_find_inner(graph, o, predicates, datatypes, True) for o in objects)))
    if all:
        return objects
    elif objects:
        return iter(objects).next()

@task(name='humfrey.ckan.upload_dataset_metadata')
def upload_dataset_metadata(update_log, graphs, updated):
    slug = update_log.update_definition.slug
    
    graphs = graphs.get(DEFAULT_STORE_NAME)

    if not graphs:
        logger.debug("No graphs updated for %r; aborting", slug)
        return

    if not getattr(settings, 'CKAN_API_KEY', None):
        logger.debug("No CKAN_API_KEY setting, not doing anything.")
        return

    client = ckanclient.CkanClient(api_key=settings.CKAN_API_KEY)

    endpoint = Endpoint(settings.ENDPOINT_QUERY)
    query = _dataset_query % '      \n'.join('(%s)' % rdflib.URIRef(g).n3() for s, g in graphs)
    graph = endpoint.query(query)

    datasets = list(graph.subjects(NS.rdf.type, NS.void.Dataset))
    if len(datasets) != 1:
        logger.debug("Expected one dataset for %r, got %d", slug, len(datasets))
        return
    dataset = Resource(datasets[0], graph, endpoint)

    find = functools.partial(_find, graph, dataset._identifier)

    patterns = settings.CKAN_PATTERNS

    package_name = find('skos:notation', HUMFREY.theDataHubDatasetName)
    if not package_name:
        package_name = patterns.get('name', '%s') % slug

    package_title = patterns.get('title', '%s') % dataset.label

    author = find('dcterms:publisher/foaf:name|rdfs:label|dc:title|skos:prefLabel|dcterms:title')
    if author:
        author = patterns.get('author', '%s') % author

    description = find('rdfs:comment|dcterms:description',
                       (NS.xtypes['Fragment-Markdown'],
                        NS.xtypes['Fragment-PlainText'],
                        None))

    maintainer = find('oo:contact/foaf:name|rdfs:label|dc:title|skos:prefLabel|dcterms:title')
    if maintainer:
        maintainer = patterns.get('maintainer', '%s') % maintainer

    maintainer_email = find('oo:contact/foaf:mbox|v:email')
    if maintainer_email:
        maintainer_email = maintainer_email.replace('mailto:', '')

    license = find('dcterms:license|cc:license')
    if license:
        license = _licenses.get(unicode(license))

    sparql_endpoint = find('void:sparqlEndpoint')
    if sparql_endpoint:
        sparql_endpoint = unicode(sparql_endpoint)
    else:
        sparql_endpoint = 'http:' + reverse_full('data', 'sparql:endpoint')

    tags = find('humfrey:theDataHubDatasetTag', all=True)
    groups = find('humfrey:theDataHubDatasetGroup', all=True)

    url = doc_forward(dataset.uri)

    logger.debug("Fetching existing record for %r", package_name)
    try:
        package_entity = client.package_entity_get(package_name)
        logger.debug("Record successfully retrieved")
    except ckanclient.CkanApiNotFoundError:
        package_entity = {'name': package_name}
        client.package_register_post(package_entity)
        logger.debug("No record found; starting from empty")
    original = copy.deepcopy(package_entity)

    package_entity.update({'name': package_name,
                           'title': package_title,
                           'url': url,
                           'notes': description,
                           'license_id': license,
                           'author': author,
                           'maintainer': maintainer,
                           'maintainer_email': dataset.oo_contact.get_one_of('foaf:mbox', 'v:email').replace('mailto:', '', 1)})

    package_entity['groups'] = list(settings.CKAN_GROUPS
                                  | set(package_entity.get('groups', ()))
                                  | groups)
    package_entity['tags'] = list(settings.CKAN_TAGS
                                | set(package_entity.get('tags', ()))
                                | tags)

    resources = collections.defaultdict(dict, ((r.get('name'), r) for r in package_entity.get('resources', ())))

    resources['SPARQL endpoint'].update({'name': 'SPARQL endpoint',
                                         'format': 'api/sparql',
                                         'url': sparql_endpoint})

    package_entity['resources'] = resources.values()

    logger.debug("Updated CKAN record")

    if original != package_entity:
        logger.info("Updating %r at thedatahub.org", package_name)
        client.package_entity_put(package_entity)


