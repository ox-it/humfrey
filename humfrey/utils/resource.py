from collections import defaultdict
from functools import partial
from urllib import urlencode, quote
import urllib2, base64, re, hashlib
from urlparse import urlparse
from xml.sax.saxutils import escape

from rdflib import URIRef, BNode

from django.core.cache import cache
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe, SafeData

from .namespaces import NS

TYPE_REGISTRY = {}
LOCALPART_RE = re.compile('^[a-zA-Z\d_-]+$')

def register(cls, *types):
    for t in types:
        prefix, local = t.split(':', 1)
        uri = NS[prefix][local]
        TYPE_REGISTRY[uri] = cls

def cache_per_identifier(f):
    def g(self, *args, **kwargs):
        key = hashlib.sha1('resource-metadata:%s:%s' % (f.__name__, self._identifier)).hexdigest()
        value = cache.get(key)
        if value is None:
            value = f(self, *args, **kwargs)
            cache.set(key, value, 18000)
        return value
    return g

def is_resource(r):
	return isinstance(r, (URIRef, BNode))    

class Resource(object):
    def __new__(cls, identifier, graph, endpoint):
        classes = set([(-1, BaseResource)])
        for t in graph.objects(identifier, NS['rdf'].type):
            if t in TYPE_REGISTRY:
                classes.add((getattr(TYPE_REGISTRY[t], '_priority', 0), TYPE_REGISTRY[t]))
        classes = tuple(b for a,b in sorted(classes, reverse=True))
        cls = type(type(identifier).__name__ + cls.__name__, classes + (type(identifier),), {})
        resource = cls(identifier, graph, endpoint)
        return resource

class BaseResource(object):
    _priority = -1
    _template_name = 'doc/base'
	
    def __new__(cls, identifier, graph, endpoint):
        return super(BaseResource, cls).__new__(cls, identifier)

    def __init__(self, identifier, graph, endpoint):
        self._identifier, self._graph, self._endpoint = identifier, graph, endpoint
        self._augment()
    
    def _augment(self):
    	pass
    	
    def widget_templates(self):
    	return []    			

    def __unicode__(self):
        return unicode(self._identifier)
        
    def __hash__(self):
        return hash((self.__class__, self._identifier))
        
#    def __getattribute__(self, name):
#        import traceback, pprint
#        if name == 'replace':
#            print '='*80
#            pprint.pprint(traceback.extract_stack()[-8:])
#            print '='*80
#        raise AttributeError
        
    def render(self):
        if isinstance(self._identifier, BNode):
            return self.label
        else:
        	return mark_safe(u'<a href="%s">%s</a>' % (escape(self.doc_url), escape(self.label)))

    @property    
    def doc_url(self):
        uri = urlparse(self._identifier)
        if uri.netloc in settings.SERVED_DOMAINS and uri.path.startswith('/id/'):
            return escape(self._identifier)
        elif self.in_store:
            return '%s?%s' % (reverse('doc'), urlencode({'uri': self._identifier}))
        else:
            return escape(self._identifier)
    	
    	

    def __repr__(self):
        return '%s("%s")' % (self.__class__.__name__, self)
        
    def replace(self, *args, **kwargs):
        return unicode(self).replace(*args, **kwargs)
        
    @property
    def template_name(self):
    	for cls in type(self).__bases__:
    		if hasattr(cls, '_template_name'):
    			return cls._template_name
        
    @property
    def uri(self):
        return self._identifier
    
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
            value = self._graph.value(None, uri, self._identifier)
        else:
            value = self._graph.value(self._identifier, uri, None)
        if is_resource(value):
            value = Resource(value, self._graph, self._endpoint)
        return value
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
            return None
        prefix, local = name.split(':', 1)
        try:
            uri = NS[prefix][local]
        except KeyError:
            return None
        if inverse:
            values = self._graph.subjects(uri, self._identifier)
        else:
            values = self._graph.objects(self._identifier, uri)
        values = [Resource(v, self._graph, self._endpoint) if is_resource(v) else v for v in values]
        values.sort(key=lambda r: (r.label if is_resource(r) else r))
        return values
    
    def properties(self):
        data = defaultdict(set)
        for p, o in self._graph.predicate_objects(self._identifier):
            if isinstance(o, (URIRef, BNode)):
                o = Resource(o, self._graph, self._endpoint)
            data[p].add(o)
        return [(Resource(p, self._graph, self._endpoint), os) for p, os in sorted(data.iteritems())]

    _LABEL_PROPERTIES = ('skos:prefLabel', 'rdfs:label', 'foaf:name', 'doap:name', 'dcterms:title', 'dc:title')

    @property
    @cache_per_identifier
    def label(self):
        label = self.get_one_of(*self._LABEL_PROPERTIES)
        if label is not None:
            return label
        self._graph += self._endpoint.describe(self._identifier)
        label = self.get_one_of(*self._LABEL_PROPERTIES)
        if label is not None:
            return label
        elif isinstance(self._identifier, URIRef):
            for prefix, uri in NS.iteritems():
                if self._identifier.startswith(uri):
                    localpart = self._identifier[len(uri):]
                    if LOCALPART_RE.match(localpart):
                        return '%s:%s' % (prefix, localpart)
            return self._identifier
        else:
            return '<unnamed>'

    @property
    @cache_per_identifier
    def in_store(self):
        return self._identifier in self._endpoint

    _DESCRIPTION_PROPERTIES = ('dcterms:description', 'dc:description', 'rdfs:comment')
    description = property(lambda self:self.get_one_of(*self._DESCRIPTION_PROPERTIES))

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
                return False
            return response.headers['content-type'] in ('image/jpeg', 'image/png', 'image/gif')
        except:
            return False
        return True
register(Image, 'foaf:Image')

class Dataset(object):
    _template_name = 'doc/dataset'
	
    def _augment(self):
        self._graph += self._endpoint.query("DESCRIBE ?s WHERE { %s dcterms:source ?s }" % self._identifier.n3())
        self._graph += self._endpoint.query("DESCRIBE ?s WHERE { %s dcterms:license ?s }" % self._identifier.n3())
        self._graph += self._endpoint.query("DESCRIBE ?s WHERE { ?s void:inDataset %s }" % self._identifier.n3())
        super(Dataset, self)._augment()
	
    _STARS = dict((NS['oo']['opendata-%s-star' % i], ('stars/data-badge-%s.png' % i, '%s-star dataset' % i)) for i in range(6)) 
	
    @property
    def open_data_stars(self):
    	for o in self._graph.objects(self._identifier, NS['dcterms'].conformsTo):
    		if o in self._STARS:
    			return self._STARS[o]
    	else:
    		return None
    
    _USED_CLASSES_QUERY = """
         CONSTRUCT { ?t a rdfs:Class ; rdfs:label ?label } WHERE {
            GRAPH ?g { ?s a ?t } .
            FILTER ( %s ) .            
            OPTIONAL { ?t rdfs:label ?label }
        }"""
    def used_classes(self):
        query = self._USED_CLASSES_QUERY % (
            ' || '.join('?g = %s' % g.n3() for g in self._graph.subjects(NS['void'].inDataset, self._identifier))
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
            ' || '.join('?g = %s' % g.n3() for g in self._graph.subjects(NS['void'].inDataset, self._identifier))
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

class CollegeHall(object):
    def _augment(self):
        self._graph += self._endpoint.query("DESCRIBE ?s WHERE { ?s qb:dataset <http://data.ox.ac.uk/id/dataset/norrington> ; fhs:institution %s }" % self._identifier.n3())
        super(CollegeHall, self)._augment()
        print self.fhs_results()
        
    def fhs_results(self):
    	print list(self._graph.subjects(NS['fhs'].institution, self._identifier))
    	data = self._graph.subjects(NS['fhs'].institution, self._identifier)
    	data = (Resource(datum, self._graph, self._endpoint) for datum in data)
    	data = filter(lambda datum: datum.fhs_norringtonScore, data) 
    	data = sorted(data, key=lambda datum:datum.sdmxdim_timePeriod)
    	for datum in data:
    		datum.fhs_two_one = datum.get('fhs:two-one')
    		datum.fhs_two_two = datum.get('fhs:two-two')
    		datum.fhs_norringtonScore = '%.1f%%' % (datum.get('fhs:norringtonScore').toPython() * 100)
    	return data
    	

    def widget_templates(self):
        return ['widgets/norrington.html'] + super(CollegeHall, self).widget_templates()
        
register(CollegeHall, 'oxp:Hall', 'oxp:College')