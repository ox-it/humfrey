from collections import defaultdict
from functools import partial
from urllib import urlencode, quote
import urllib2, base64, re
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
        key = base64.b64encode('resource-metadata:%s:%s' % (f.__name__, self._identifier))
        value = cache.get(key)
        if value is None:
            value = f(self, *args, **kwargs)
            cache.set(key, value, 1800)
        return value
    return g
    

class Resource(object):
    def __new__(cls, identifier, graph, endpoint):
        for t in graph.objects(identifier, NS['rdf'].type):
            if t in TYPE_REGISTRY:
                cls = TYPE_REGISTRY[t]
                break
        else:
            cls = BaseResource
        cls = type(type(identifier).__name__ + cls.__name__, (cls, type(identifier)), {})
        resource = cls(identifier, graph, endpoint)
        return resource

class BaseResource(object):
    def __new__(cls, identifier, graph, endpoint):
        return super(BaseResource, cls).__new__(cls, identifier)

    def __init__(self, identifier, graph, endpoint):
        self._identifier, self._graph, self._endpoint = identifier, graph, endpoint

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
        uri = urlparse(self._identifier)
        if isinstance(self._identifier, BNode):
            return self.label
        if uri.netloc in settings.SERVED_DOMAINS and uri.path.startswith('/id/'):
            return mark_safe(u'<a href="%s">%s</a>' % (escape(self._identifier), escape(self.label)))
        elif self.in_store:
            return mark_safe(u'<a href="%s?%s">%s</a>' % (reverse('doc'), urlencode({'uri': self._identifier}), escape(self.label)))
        else:
            return mark_safe(u'<a href="%s">%s</a>' % (escape(self._identifier), escape(self.label)))

    def __repr__(self):
        return '%s("%s")' % (self.__class__.__name__, self)
        
    def replace(self, *args, **kwargs):
        return unicode(self).replace(*args, **kwargs) 
        
    @property
    def uri(self):
        return unicode(self._identifier)
    
    def get(self, name):
        if ':' not in name:
            name = name.replace('_', ':', 1)
        prefix, local = name.split(':', 1)
        try:
            uri = NS[prefix][local]
        except KeyError:
            return None
        value = self._graph.value(self._identifier, uri, None)
        if isinstance(value, (URIRef, BNode)):
            value = Resource(value, self._graph, self._endpoint)
        return value
    __getattr__ = get
    
    def get_one_of(self, *qnames):
        for qname in qnames:
            value = self.get(qname)
            if value is not None:
                return value
        return None
    
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

class Account(BaseResource):
    def render(self):
        if self.foaf_accountServiceHomepage.uri == 'http://www.twitter.com/':
            return mark_safe('<a href="%s"><img class="icon" src="http://twitter-badges.s3.amazonaws.com/t_mini-b.png" alt="%s on Twitter"/> @%s</a>' % tuple(map(escape,
                (self.foaf_accountProfilePage.uri, self.foaf_accountName, self.foaf_accountName))))
        else:
            return mark_safe('<a href="%s">%s at %s</a>' % tuple(map(escape, (self.foaf_accountProfilePage.uri, self.foaf_accountName, self.foaf_accountServiceHomepage.uri))))
    
    _WIDGET_TEMPLATES = {
        'http://www.twitter.com/': 'widgets/twitter.html',
    }
    def widget_template(self):
        return self._WIDGET_TEMPLATES.get(self.foaf_accountServiceHomepage.uri)
        
register(Account, 'foaf:OnlineAccount')

class Address(BaseResource):
    def render(self):
        address = []
        for p in ('v:extended-address', 'v:street-address', 'v:locality', 'v:postal-code'):
            value = self.get(p)
            if value:
                address.append(value)
        return mark_safe('<br/>'.join(escape(v) for v in address))
register(Address, 'v:Address')

class Tel(BaseResource):
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

class Class(BaseResource):
    def things_of_type(self):
        graph = self._endpoint.query("DESCRIBE ?uri WHERE { ?uri a %s } LIMIT 20" % self._identifier.n3())
        return [Resource(s, graph, self._endpoint) for s in graph.subjects(NS['rdf'].type, self._identifier)]
register(Class, 'rdfs:Class', 'owl:Class')

class Image(BaseResource):
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
            return response.headers['content-type'] in ('image/jpeg', 'image/png')
        except:
            return False
        return True
register(Image, 'foaf:Image')
