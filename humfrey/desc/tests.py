import collections
import itertools


import mock
import rdflib, rdflib.term
import simplejson
import unittest2

from django.test.client import Client
from django.http import HttpResponseNotFound

from humfrey.desc import rdf_processors, views
from humfrey.utils import sparql, resource, namespaces
from humfrey.tests.stubs import stub_reverse_crossdomain

TEST_RESULTSET_RESULT = collections.namedtuple('Result', 'one two')
TEST_RESULTSET = sparql.ResultList(list(itertools.starmap(TEST_RESULTSET_RESULT, [
    (rdflib.URIRef('http://example.org/one'), rdflib.BNode()),
    (rdflib.Literal('hello'), rdflib.Literal('hello', lang='en')),
    (rdflib.Literal('foo"bar'), rdflib.Literal('foo\nbar')),
    (rdflib.Literal('foo bar'), rdflib.Literal('foo\tbar')),
    (rdflib.Literal(1), rdflib.Literal('2011-01-02T12:34:56Z', datatype=namespaces.NS.xsd.timeDate)),
    (None, None),
    (rdflib.URIRef('http://example.org/'), rdflib.URIRef('mailto:alice@example.org')),
    (rdflib.URIRef('urn:isbn:9781449306595'), rdflib.URIRef('tag:bob@example.org,2011:foo')),
])))
TEST_RESULTSET.fields = ('one', 'two')
TEST_RESULTSET.query = 'The query that was run'
TEST_RESULTSET.duration = 1
    

class GraphTestMixin(object):
    def check_valid_terms(self, graph):
        for term in itertools.chain.from_iterable(graph):
            self.assertIsInstance(term, rdflib.term.Identifier)

class ClientTestCase(unittest2.TestCase):
    def setUp(self):
        self.client = Client()

@mock.patch('humfrey.linkeddata.uri.reverse_crossdomain', stub_reverse_crossdomain)
class RDFProcessorsTestCase(unittest2.TestCase, GraphTestMixin):
    _ALL = [
        rdf_processors.formats,
        rdf_processors.doc_meta,
    ]

    def testAll(self):
        for rdf_processor in self._ALL:
            endpoint = mock.Mock(spec=sparql.Endpoint)
            graph = rdflib.ConjunctiveGraph()
            doc_uri = rdflib.URIRef('http://example.com/doc/Foo')
            subject_uri = rdflib.URIRef('http://example.com/id/Foo')
            subject = resource.Resource(subject_uri, graph, endpoint)
            renderers = views.DocView().FORMATS.values()

            context = rdf_processor(graph, doc_uri, subject_uri, subject, endpoint, renderers)

            self.assertFalse(endpoint.query.called, "The rdf procesor should not be touching the endpoint (at the moment)")
            self.check_valid_terms(graph)
            self.assertIsInstance(context, (type(None), dict))

#@mock.patch('humfrey.linkeddata.uri.reverse_crossdomain', stub_reverse_crossdomain)
class DocViewTestCase(ClientTestCase, GraphTestMixin):
    _TEST_URI = 'http://data/example.com/id/Foo'
    _HTTP_HOST = 'data.example.org'

    @mock.patch('humfrey.desc.views.DocView.get_types')
    def testNoTypes(self, get_types):
        get_types.return_value = ()
        response = self.client.get('/doc/', {'uri': self._TEST_URI}, HTTP_HOST=self._HTTP_HOST)
        self.assertIsInstance(response, HttpResponseNotFound)


    @mock.patch('humfrey.desc.views.DocView.get_types')
    @mock.patch('humfrey.desc.views.DocView.endpoint')
    def testGraphValid(self, endpoint, get_types):
        get_types.return_value = (rdflib.URIRef('http://example.org/vocab/Thing'),)
        endpoint.query.return_value = rdflib.ConjunctiveGraph()
        response = self.client.get('/doc/', {'uri': self._TEST_URI, 'format': 'html'}, HTTP_HOST='data.example.org')
        self.assertIsInstance(response.context['subject_uri'], rdflib.URIRef)
        self.assertIsInstance(response.context['doc_uri'], rdflib.URIRef)
        self.check_valid_terms(response.context['graph'])

class SparqlViewTestCase(ClientTestCase, GraphTestMixin):

    @mock.patch('humfrey.desc.views.redis.client.Redis')
    @mock.patch('humfrey.desc.views.SparqlView.endpoint')
    def testValidSparqlResultsJSON(self, endpoint, redis_client_class):
        endpoint.query.return_value = TEST_RESULTSET
        redis_client = redis_client_class.return_value
        redis_client.setnx.return_value = True
        redis_client.get.return_value = 0

        response = self.client.get('/sparql/', {'query': 'irrelevant'}, HTTP_HOST='data.example.org', HTTP_ACCEPT='application/sparql-results+json')
        endpoint.query.assert_called_once_with('irrelevant', common_prefixes=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/sparql-results+json')
        
        try:
            data = simplejson.loads(response.content)
        except Exception, e:
        	   raise AssertionError(e)
        
        self.assertEqual(data['head']['vars'], ['one', 'two'])
        self.assertEqual(len(data['results']), 8)
        	    
