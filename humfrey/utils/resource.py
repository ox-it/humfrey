from collections import defaultdict
import urllib2, base64, re, hashlib, random, itertools, logging
from xml.sax.saxutils import escape, quoteattr

from rdflib import URIRef, BNode

from django.core.cache import cache
from django.conf import settings
from django.utils.safestring import mark_safe

from humfrey.utils.namespaces import NS, expand
from humfrey.linkeddata.uri import doc_forward

image_logger = logging.getLogger('humfrey.utils.resource.image')

TYPE_REGISTRY = {}
LOCALPART_RE = re.compile('^[a-zA-Z\d_-]+$')

IRI = re.compile(u'^([^\\<>"{}|^`\x00-\x20])*$')

def register(cls, *types):
    for t in types:
        TYPE_REGISTRY[expand(t)] = cls

def cache_per_identifier(f):
    def g(self, *args, **kwargs):

        key = hashlib.sha1('resource-metadata:%s:%s' % (f, base64.b64encode(self._identifier.encode('utf-8')))).hexdigest()
        value = cache.get(key)
        if value is None:
            value = f(self, *args, **kwargs)
            cache.set(key, value, 18000)
        return value
    return g

class SparqlQueryVars(dict):
    def __init__(self, **kwargs):
        super(SparqlQueryVars, self).__init__(**dict((k, v.n3()) for k, v in kwargs.iteritems()))
    def __getitem__(self, key):
        try:
            return super(SparqlQueryVars, self).__getitem__(key)
        except KeyError:
            var = '?' + key
            self[key] = var
            return var

def is_resource(r):
    return isinstance(r, (URIRef, BNode))

class Resource(object):
    def __new__(cls, identifier, graph, endpoint):
        classes = [BaseResource]
        for t in graph.objects(identifier, NS['rdf'].type):
            if t in TYPE_REGISTRY and TYPE_REGISTRY[t] not in classes:
                classes.append(TYPE_REGISTRY[t])
        classes.sort(key=lambda cls:-getattr(cls, '_priority', 0))
        cls = type(type(identifier).__name__ + classes[0].__name__, tuple(classes) + (type(identifier),), {})
        resource = cls(identifier, graph, endpoint)
        return resource

class BaseResource(object):
    _priority = -1
    template_name = 'doc/base'

    def __new__(cls, identifier, graph, endpoint):
        return super(BaseResource, cls).__new__(cls, identifier)

    def __init__(self, identifier, graph, endpoint):
        self._identifier, self._graph, self._endpoint = identifier, graph, endpoint

    def widget_templates(self):
        return []

    def __unicode__(self):
        return unicode(self._identifier)

    def __hash__(self):
        return hash((self.__class__, self._identifier))

    def render(self):
        if isinstance(self._identifier, BNode):
            return self.label
        return mark_safe(u'<a href=%s>%s</a>' % (quoteattr(self.doc_url), escape(self.label)))

    @property
    def doc_url(self):
        return doc_forward(self._identifier, graph=self._graph)

    def __repr__(self):
        return '%s("%s")' % (self.__class__.__name__, self)

    def replace(self, *args, **kwargs):
        return unicode(self).replace(*args, **kwargs)

    @property
    def uri(self):
        return unicode(self._identifier)

    @property
    def all(self):
        class C(object):
            def __getattr__(_, name):
                return self.get_all(name)
        return C()

    def get(self, name):
        if name.endswith('_inv'):
            name, inverse = name[:-4], True
        else:
            inverse = False
        if ':' not in name:
            name = name.replace('_', ':', 1)
        if ':' not in name:
            return None
        prefix, local = name.split(':', 1)
        try:
            uri = NS[prefix][local]
        except KeyError:
            return None
        if inverse:
            values = list(self._graph.subjects(uri, self._identifier))
        else:
            values = list(self._graph.objects(self._identifier, uri))
        if not values:
            return None
        if is_resource(values[0]):
            return Resource(values[0], self._graph, self._endpoint)
        else:
            return self.localised(values)[0]
    __getattr__ = get

    def get_one_of(self, *qnames):
        for qname in qnames:
            value = self.get(qname)
            if value is not None:
                return value
        return None

    def get_all(self, name):
        if name.endswith('_inv'):
            name, inverse = name[:-4], True
        else:
            inverse = False
        if ':' not in name:
            name = name.replace('_', ':', 1)
        if ':' not in name:
            return []
        prefix, local = name.split(':', 1)
        try:
            uri = NS[prefix][local]
        except KeyError:
            return []
        if inverse:
            values = self._graph.subjects(uri, self._identifier)
        else:
            values = self._graph.objects(self._identifier, uri)
        values = list(values)
        values = [Resource(v, self._graph, self._endpoint) if is_resource(v) else v for v in values]
        values.sort(key=lambda r: (r.label if is_resource(r) else r))
        return values

    def properties(self):
        data, objects = defaultdict(set), set()
        for p, o in self._graph.predicate_objects(self._identifier):
            objects.add(p)
            if isinstance(o, (URIRef, BNode)):
                o = Resource(o, self._graph, self._endpoint)
            if isinstance(o, URIRef):
                objects.add(o)
            data[p].add(o)
        for p in data:
            data[p] = self.localised(data[p])

        self._graph += self._endpoint.query("""
            CONSTRUCT {
              ?s rdfs:label ?label
            } WHERE {
              ?s ?p ?label .
              FILTER ( %s ) .
              FILTER ( ?p = rdfs:label || ?p = rdf:value || ?p = foaf:name || ?p = skos:prefLabel || ?p = dc:title || ?p = dcterms:title )
            }
        """ % ' || '.join('?s = %s' % o.n3() for o in objects if IRI.match(o)))

        return [(Resource(p, self._graph, self._endpoint), os) for p, os in sorted(data.iteritems())]

    _LABEL_PROPERTIES = ('skos:prefLabel', 'rdfs:label', 'foaf:name', 'doap:name', 'dcterms:title', 'dc:title', 'rdf:value')

    def depictions(self):
        ds = list(itertools.chain(*map(self.get_all, settings.IMAGE_PROPERTIES)))
        return ds

    @property
    def label(self):
        labels = list(itertools.chain(*[self.get_all(p) for p in self._LABEL_PROPERTIES]))
        #if not labels:
        #    self._graph += self._endpoint.describe(self._identifier)
        #    labels = list(itertools.chain(*[self.get_all(p) for p in self._LABEL_PROPERTIES]))
        if not labels:
            if isinstance(self._identifier, URIRef):
                return self.label2
            elif self.rdf_type:
                return '<unnamed %s>' % self.rdf_type.label
            else:
                return '<unnamed>'
        return self.localised(labels)[0]

    def localised(self, values):
        def f(v):
            if isinstance(v, (URIRef, BNode)):
                return -4
            else:
                return {'en-GB': -3, 'en-US': -2, 'en': -1}.get(v.language, 0)
        return sorted(values, key=f)

    @property
    def label2(self):
        for prefix, uri in NS.iteritems():
            if self._identifier.startswith(uri):
                localpart = self._identifier[len(uri):]
                if LOCALPART_RE.match(localpart):
                    return '%s:%s' % (prefix, localpart)
        return self._identifier

    @property
    @cache_per_identifier
    def in_store(self):
        return self._identifier in self._graph.subjects() or self._identifier in self._endpoint

    _DESCRIPTION_PROPERTIES = ('dcterms:description', 'dc:description', 'rdfs:comment')
    description = property(lambda self:self.get_one_of(*self._DESCRIPTION_PROPERTIES))

    def sorted_subjects(self, ps, os):
        ps = ps if isinstance(ps, tuple) else (ps,)
        os = os if isinstance(os, tuple) else (os,)
        subjects = set(itertools.chain(*[self._graph.subjects(p, o) for p in ps for o in os]))
        subjects = (Resource(s, self._graph, self._endpoint) for s in subjects)
        subjects = sorted(subjects, key=lambda s: s.label)
        return subjects

    def get_queries(self):
        for f in (self.get_describe_query, self.get_construct_query):
            query = f()
            if query:
                yield query

    def get_describe_query(self):
        patterns, vars = set(), SparqlQueryVars(uri=self._identifier)

        for base in type(self).__bases__:
            if hasattr(base, '_describe_patterns'):
                patterns |= set(p % vars for p in base._describe_patterns())
        query = 'DESCRIBE %s' % ' '.join(sorted(vars.values()))
        if patterns:
            query += ' {\n  %s\n}' % '\n  UNION\n  '.join('{ %s }' % p for p in patterns)
        return query

    def get_construct_query(self):
        constructs, patterns, vars = set(), set(), SparqlQueryVars(uri=self._identifier)

        for base in type(self).__bases__:
            if hasattr(base, '_construct_patterns'):
                for pattern in base._construct_patterns():
                    if not isinstance(pattern, tuple):
                        pattern = (pattern, pattern)
                    constructs.add(pattern[0] % vars)
                    patterns.add(pattern[1] % vars)
        if patterns:
            return 'CONSTRUCT {\n  %s\n} WHERE {\n  %s\n}' % (
                ' .\n  '.join(constructs),
                '\n  UNION\n  '.join('{ %s }' % p for p in patterns))
        else:
            return None

    @property
    def hexhash(self):
        return hashlib.sha1(self._identifier).hexdigest()[:8]

class Account(object):
    def render(self):
        if self.foaf_accountServiceHomepage.uri == URIRef('http://www.twitter.com/'):
            return mark_safe('<a href="%s"><img class="icon" src="http://twitter-badges.s3.amazonaws.com/t_mini-b.png" alt="%s on Twitter"/> @%s</a>' % tuple(map(escape,
                (self.foaf_accountProfilePage.uri, self.foaf_accountName, self.foaf_accountName))))
        else:
            return mark_safe('<a href="%s">%s at %s</a>' % tuple(map(escape, (self.foaf_accountProfilePage.uri, self.foaf_accountName, self.foaf_accountServiceHomepage.uri))))

    _WIDGET_TEMPLATES = {
        URIRef('http://www.twitter.com/'): 'widgets/twitter.html',
    }
    def widget_templates(self):
        return [self._WIDGET_TEMPLATES.get(self.foaf_accountServiceHomepage.uri)] + super(Account, self).widget_templates()

register(Account, 'foaf:OnlineAccount')

class Address(object):
    def render(self):
        address = []
        for p in ('v:extended-address', 'v:street-address', 'v:locality', 'v:postal-code'):
            value = self.get(p)
            if value:
                address.append(value)
        return mark_safe('<br/>'.join(escape(v) for v in address))
register(Address, 'v:Address')

class Tel(object):
    _TYPES = {'Voice': 'voice', 'Fax': 'fax'}
    _TYPES = dict((NS['v'][a], l) for a, l in _TYPES.iteritems())
    def render(self):
        value = self.get('rdf:value')
        types = []
        for t in self._graph.objects(self._identifier, NS['rdf'].type):
            if t in self._TYPES:
                types.append(self._TYPES[t])
        types = ', '.join(escape(t) for t in types) if types else 'unknown'
        return mark_safe('<a href="tel:%s">%s</a> (%s)' % (escape(value), escape(value), types))
register(Tel, 'v:Tel', 'v:Voice', 'v:Fax')

class Class(object):
    def things_of_type(self):
        graph = self._endpoint.query("DESCRIBE ?uri WHERE { ?uri a %s } LIMIT 20" % self._identifier.n3())
        resources = [Resource(s, graph, self._endpoint) for s in graph.subjects(NS['rdf'].type, self._identifier)]
        resources.sort(key=lambda r:r.label)
        return resources
register(Class, 'rdfs:Class', 'owl:Class')

class Image(object):
    class HEADRequest(urllib2.Request):
        def get_method(self):
            return 'HEAD'

    @property
    @cache_per_identifier
    def is_image(self):
        request = Image.HEADRequest(self._identifier)
        try:
            response = urllib2.urlopen(request)
            if 'content-type' not in response.headers:
                image_logger.warning("Image resource doesn't respond with Content-Type: %r", unicode(self._identifier))
                return False
            if response.headers['content-type'] not in ('image/jpeg', 'image/png', 'image/gif'):
                image_logger.warning("Image resource has wrong content type: %r (%r)", response.headers['Content-Type'], unicode(self._identifier))
        except:
            logging.exception("HEAD request for image failed: %r", unicode(self._identifier))
            return False
        return True
register(Image, *settings.IMAGE_TYPES)

class Dataset(object):
    template_name = 'doc/dataset'

    @classmethod
    def _describe_patterns(cls):
        return [
            '%(uri)s dcterms:source %(name)s',
            '%(uri)s dcterms:license %(name)s',
            '%(name)s void:inDataset %(uri)s',
        ]

    _STARS = dict((NS['oo']['opendata-%s-star' % i], ('stars/data-badge-%s.png' % i, '%s-star dataset' % i)) for i in range(6))

    @property
    def open_data_stars(self):
        for o in self._graph.objects(self._identifier, NS['dcterms'].conformsTo):
            if o in self._STARS:
                return self._STARS[o]
        else:
            return None

    @property
    def graph_names(self):
        if not hasattr(self, '_graph_names'):
            self._graph_names = list(self._graph.subjects(NS['void'].inDataset, self._identifier))
        return self._graph_names

    _USED_CLASSES_QUERY = """
         CONSTRUCT { ?t a rdfs:Class ; rdfs:label ?label } WHERE {
            GRAPH ?g { ?s a ?t } .
            FILTER ( %s ) .
            OPTIONAL { ?t rdfs:label ?label }
        }"""
    def used_classes(self):
        query = self._USED_CLASSES_QUERY % (
            ' || '.join('?g = %s' % g.n3() for g in random.sample(self.graph_names, 10))
        )
        try:
            graph = self._endpoint.query(query)
        except urllib2.HTTPError:
            return []
        classes = [Resource(c, graph, self._endpoint) for c in set(graph.subjects())]
        classes.sort(key=lambda c:c.label)
        return classes

    _USED_PREDICATES_QUERY = """
        CONSTRUCT { ?p a rdfs:Property ; rdfs:label ?label } WHERE {
            GRAPH ?g { ?s ?p ?o } .
            FILTER ( %s ) .
            OPTIONAL { ?p rdfs:label ?label }
        }"""
    def used_predicates(self):
        query = self._USED_PREDICATES_QUERY % (
            ' || '.join('?g = %s' % g.n3() for g in random.sample(self.graph_names, 10))
        )
        try:
            graph = self._endpoint.query(query)
        except urllib2.HTTPError:
            return []
        predicates = [Resource(p, graph, self._endpoint) for p in set(graph.subjects())]
        predicates.sort(key=lambda p:p.label)
        return predicates

register(Dataset, 'void:Dataset')

class License(object):
    class C(set):
        def __getattr__(self, name):
            if ':' not in name:
                name = name.replace('_', ':', 1)
            if ':' not in name:
                return None
            prefix, local = name.split(':', 1)
            try:
                uri = NS[prefix][local]
            except KeyError:
                return False
            return uri in self

    @property
    def requires(self):
        return License.C(self._graph.objects(self._identifier, NS['cc'].requires))
register(License, 'cc:License')

class Ontology(object):
    _template_name = 'doc/ontology'

    @cache_per_identifier
    def _augment(self):
        return self._endpoint.query("DESCRIBE ?s WHERE { ?s rdfs:isDefinedBy %s }" % self._identifier.n3())
    #@cache_per_identifier
    def defined_classes(self):
        classes = self.sorted_subjects(NS['rdf'].type, (NS['rdfs'].Class, NS['owl'].Class))
        return [c for c in classes if (c.uri, NS['rdfs'].isDefinedBy, self._identifier) in self._graph]
    #@cache_per_identifier
    def defined_properties(self):
        properties = self.sorted_subjects(NS['rdf'].type, (NS['rdf'].Property, NS['owl'].AnnotationProperty, NS['owl'].ObjectProperty))
        return [p for p in properties if (p.uri, NS['rdfs'].isDefinedBy, self._identifier) in self._graph]

register(Ontology, 'owl:Ontology')
