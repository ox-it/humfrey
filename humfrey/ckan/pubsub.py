from django.conf import settings
from django_hosts.reverse import reverse_full
from django_longliving.decorators import pubsub_watcher

from humfrey.update.longliving.updater import Updater
from humfrey.utils.sparql import Endpoint
from humfrey.utils.namespaces import NS
from humfrey.utils.resource import Resource

from humfrey.linkeddata.uri import doc_forward

import ckanclient
import rdflib

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

}

@pubsub_watcher(channel=Updater.UPDATED_CHANNEL)
def update_ckan_dataset(channel, data):
    if not data['graphs']:
        return

    client = ckanclient.CkanClient(api_key=settings.CKAN_API_KEY)

    endpoint = Endpoint(settings.ENDPOINT_QUERY)
    query = _dataset_query % '      \n'.join('(%s)' % rdflib.URIRef(g).n3() for g in data['graphs'])
    graph = endpoint.query(query)
    print query

    datasets = list(graph.subjects(NS.rdf.type, NS.void.Dataset))
    if len(datasets) != 1:
        raise ValueError("Expected one dataset, got %d" % len(datasets))
    dataset = Resource(datasets[0], graph, endpoint)

    patterns = settings.CKAN_PATTERNS

    package_name = patterns.get('name', '%s') % data['id']
    package_title = patterns.get('title', '%s') % dataset.label

    author = patterns.get('author', '%s') % dataset.dcterms_publisher.label
    maintainer = patterns.get('maintainer', '%s') % dataset.oo_contact.label

    url = doc_forward(dataset.uri)

    license = dataset.get_one_of('dcterms:license', 'cc:license')
    if license:
        license = _licenses.get(license.uri)

    sparql_endpoint = dataset.void_sparqlEndpoint
    if sparql_endpoint:
        sparql_endpoint = sparql_endpoint.uri
    else:
        sparql_endpoint = 'http://' + reverse_full('data', 'sparql:endpoint')

    package_entity = {'name': package_name,
                      'title': package_title,
                      'url': url,
                      'author': author,
                      'maintainer': maintainer,
                      'maintainer_email': dataset.oo_contact.get_one_of('foaf:mbox', 'v:email').replace('mailto:', '', 1),
                      'groups': list(settings.CKAN_GROUPS),
                      #'license_id': license,
                      #'extra': [{'key': unicode(NS.void.sparqlEndpoint),
                      #           'value': sparql_endpoint}]
                      }

    print package_entity
    #client.package_register_post(package_entity)

    client.package_entity_put(package_entity, package_entity['name'])


