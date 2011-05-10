import urllib2, urllib, rdflib, itertools, re, simplejson, logging
from datetime import datetime
from lxml import etree
try:
    from collections import namedtuple
except ImportError:
    from namedtuple import namedtuple
from collections import defaultdict
from django.conf import settings

from .namespaces import NS
from .resource import Resource

def is_qname(uri):
    return len(uri.split(':')) == 2 and '/' not in uri.split(':')[1]

class ResultList(list):
    pass

logger = logging.getLogger('humfrey.sparql.queries')

class Endpoint(object):
    def __init__(self, url, update_url=None, namespaces={}):
        self._url, self._update_url = url, update_url
        _namespaces = NS.copy()
        _namespaces.update(namespaces)
        self._namespaces = '\n'.join('prefix %s: <%s>' % i for i in _namespaces.items()) + '\n\n'
        self._cache = defaultdict(dict)

    def query(self, query, timeout=None, common_prefixes = True):
        if common_prefixes:
            query = self._namespaces + query

        logger.info('SPARQL query: %r', query)

        request = urllib2.Request(self._url, urllib.urlencode({
            'query': query.encode('utf-8'),
        }))
        request.headers['Accept'] = 'application/rdf+xml, application/sparql-results+xml, text/plain'
        request.headers['User-Agent'] = 'sparql.py'
        
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            raise
            print e.read()

        content_type, params = response.headers['Content-type'].split(';', 1)
        params = dict(p.split('=', 1) for p in params.split(';'))
        charset = params.get('charset', 'UTF-8')

        if content_type == 'application/sparql-results+xml':
            return self.parse_results(response)
        elif content_type == 'application/sparql-results+json':
            return self.parse_json_results(response)
        else: # response.headers['Content-Type'] == 'application/rdf+xml':
            g = rdflib.ConjunctiveGraph()
            g.parse(response)
            return g

    def update(self, query):
        request = urllib2.Request(self._update_url, urllib.urlencode({
            'request': self._namespaces + query.encode('UTF-8'),
        }))
        request.headers['User-Agent'] = 'sparql.py'

        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            pass

    def insert_data(self, triples, graph=None):
        triples = ' . '.join(' '.join(map(self.quote, triple)) for triple in triples)
        triples = "GRAPH %s { %s }" % (self.quote(graph), triples) if graph else triples
        return self.update("INSERT DATA { %s }" % triples)
        
    def delete_data(self, triples, graph=None):
        triples = ' . '.join(' '.join(map(self.quote, triple)) for triple in triples)
        triples = "GRAPH %s { %s }" % (self.quote(graph), triples) if graph else triples
        return self.update("DELETE DATA { %s }" % triples)

    def clear(self, graph):
        return self.update("CLEAR GRAPH %s" % self.quote(graph))
        

    def describe(self, uri):
        return self.query("DESCRIBE <%s>" % uri)
    def ask(self, uri):
        return self.query("ASK WHERE { %s ?p ?o }" % uri.n3())

    def forward(self, subject, predicate=None):
        subject, predicate = self.quote(subject), self.quote(predicate)
        if predicate:
            return self.query("SELECT ?object WHERE { %s %s ?object }" % (subject, predicate))
        else:
            return self.query("SELECT ?predicate ?object WHERE { %s ?predicate ?object }" % subject)

    def backward(self, predicate, obj=None):
        if not obj:
            obj, predicate = predicate, None
        predicate, obj = self.quote(predicate), self.quote(obj)
        if predicate:
            return self.query("SELECT ?subject WHERE { ?subject %s %s }" % (predicate, obj))
        else:
            return self.query("SELECT ?subject ?predicate WHERE { ?subject ?predicate %s }" % obj)

    def get(self, uri):
        return Resource(self, uri)
    
    def quote(self, uri):
        if isinstance(uri, rdflib.Node.Node):
            return uri.n3()
        elif not uri:
            return uri
        elif is_qname(uri):
            return uri
        else:
            return '<%s>' % uri

    def parse_results(self, response):

        xml = etree.parse(response).getroot()

        if len(xml.xpath('srx:boolean', namespaces=NS)):
            #raise Exception(map(etree.tostring, xml.xpath('srx:boolean', namespaces=NS)))
            return xml.xpath('srx:boolean', namespaces=NS)[0].text.strip() == 'true'

        fields = [re.sub(r'[^a-zA-Z\d_]+', '_', re.sub(r'^([^a-zA-Z])', r'f_\1', e.attrib['name'])) for e in xml.xpath('srx:head/srx:variable', namespaces=NS)]
        empty_results_dict = dict((f, None) for f in fields)
        Result = namedtuple('Result', fields)
        
        g = rdflib.ConjunctiveGraph()

        results = ResultList()
        results.fields = fields
        for result_xml in xml.xpath('srx:results/srx:result', namespaces=NS):
            result = empty_results_dict.copy()
            for binding in result_xml.xpath('srx:binding', namespaces=NS):
                result[re.sub(r'[^a-zA-Z\d_]+', '_', re.sub(r'^([^a-zA-Z])', r'f_\1', binding.attrib['name']))] = self.parse_binding(binding[0], g)
            results.append(Result(**result))

        return results

    def parse_binding(self, binding, graph):
        if binding.tag.endswith('}bnode'):
            return Resource(rdflib.BNode(binding.text), graph, self)
        elif binding.tag.endswith('}uri'):
            return Resource(rdflib.URIRef(binding.text), graph, self)
        elif binding.tag.endswith('}literal'):
            return rdflib.Literal(binding.text, datatype=binding.attrib.get('datatype'), lang=binding.attrib.get('xml:lang'))
        else:
            raise AssertionError("Unexpected binding type")

    def __contains__(self, obj):
        if isinstance(obj, tuple):
            return self.query("ASK WHERE { %s }" % ' '.join(map(self.quote, obj)))
        else:
            return self.query("ASK WHERE { %s ?p ?o }" % self.quote(obj))

    def parse_json_results(self, response):
        graph = rdflib.ConjunctiveGraph()
        json = simplejson.load(response)

        if 'boolean' in json:
        	return json['boolean'] == True

        vars_ = json['head']['vars']
        Result = namedtuple('Result', json['head']['vars'])
        pb = self.parse_json_binding

        results = ResultList()
        for binding in json['results']['bindings']:
            results.append( Result(*[pb(binding.get(v), graph) for v in vars_]) )
        results.fields = vars_
        return results

    def parse_json_binding(self, binding, graph):
        if not binding:
            return None
        t = binding['type']
        if t == 'uri':
            return Resource(rdflib.URIRef(binding['value']), graph, self)
        elif t == 'bnode':
            return Resource(rdflib.BNode(binding['value']), graph, self)
        elif t == 'literal':
            return rdflib.Literal(binding['value'], datatype=binding.get('datatype'), lang=binding.get('lang'))
        else:
            raise AssertionError("Unexpected binding type")

