# *-* coding: utf-8 *-*

import mock
import rdflib
import unittest2

try:
    from rdflib.namespace import RDF
except ImportError:
    from rdflib.RDF import RDFNS as RDF

from django.test.client import Client, RequestFactory
from django.http import HttpResponse
from django_conneg.conneg import Conneg

from humfrey.desc import rdf_processors, views
from humfrey.linkeddata import resource
import humfrey.sparql.endpoint
from humfrey.linkeddata.tests import set_mappingconf, TEST_ID_MAPPING

class GraphTestMixin(object):
    http_host = 'data.example.org'
    def check_valid_terms(self, graph):
        for s, p, o in graph:
            self.assertIsInstance(s, (rdflib.URIRef, rdflib.BNode))
            self.assertIsInstance(p, (rdflib.URIRef,))
            self.assertIsInstance(o, (rdflib.URIRef, rdflib.BNode, rdflib.Literal))

class ClientTestCase(unittest2.TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()

class RDFProcessorsTestCase(ClientTestCase, GraphTestMixin):
    _ALL = [
        rdf_processors.formats,
        rdf_processors.doc_meta,
    ]

    @set_mappingconf
    def testAll(self):
        for rdf_processor in self._ALL:
            endpoint = mock.Mock(spec=humfrey.sparql.endpoint.Endpoint)
            graph = rdflib.ConjunctiveGraph()
            doc_uri = rdflib.URIRef('http://example.org/doc/Foo')
            subject_uri = rdflib.URIRef('http://example.org/id/Foo')
            subject = resource.Resource(subject_uri, graph, endpoint)

            #import pdb;pdb.set_trace()
            doc_view = views.DocView()
            renderers = Conneg(obj=doc_view).renderers

            request = self.factory.get('')
            
            doc_view.context = {'graph': graph,
                                'doc_uri': doc_uri,
                                'subject_uri': subject_uri,
                                'subject': subject,
                                'endpoint': endpoint}
            doc_view.context['renderers'] = [doc_view.renderer_for_context(request, renderer) for renderer in renderers]

            rdf_processor(request=request, context=doc_view.context)

            self.assertFalse(endpoint.query.called, "The RDF processor should not be touching the endpoint (at the moment)")
            self.check_valid_terms(graph)
            self.assertIsInstance(doc_view.context, (type(None), dict))

class IDViewTestCase(ClientTestCase, GraphTestMixin):
    @mock.patch('humfrey.sparql.views.core.StoreView.get_types')
    def testMissing(self, get_types):
        get_types.return_value = set()
        response = self.client.get('/id/foo', HTTP_HOST=self.http_host)
        get_types.assert_called_once_with(rdflib.URIRef('http://{0}/id/foo'.format(self.http_host)))
        self.assertEqual(response.status_code, 404)

    @mock.patch('humfrey.sparql.views.core.StoreView.get_types')
    def testPresent(self, get_types):
        get_types.return_value = (rdflib.URIRef('http://example.org/vocab/Thing'),)
        response = self.client.get('/id/foo', HTTP_HOST=self.http_host)
        self.assertEqual(response.status_code, 303)
        get_types.assert_called_once_with(rdflib.URIRef('http://{0}/id/foo'.format(self.http_host)))


class DocViewTestCase(ClientTestCase, GraphTestMixin):
    _TEST_URI = 'http://data.example.org/id/foo'

    @mock.patch('humfrey.sparql.views.core.StoreView.get_types')
    @mock.patch('humfrey.desc.views.DocView.endpoint')
    def testGraphValid(self, endpoint, get_types):
        get_types.return_value = (rdflib.URIRef('http://example.org/vocab/Thing'),)
        endpoint.query.return_value = rdflib.ConjunctiveGraph()
        response = self.client.get('/doc/', {'uri': self._TEST_URI}, HTTP_HOST=self.http_host)
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['subject_uri'], rdflib.URIRef)
        self.assertIsInstance(response.context['doc_uri'], rdflib.URIRef)
        self.check_valid_terms(response.context['graph'])

    @mock.patch('humfrey.desc.views.DocView.get_types')
    def testNoTypes(self, get_types):
        get_types.return_value = ()
        response = self.client.get('/doc/', {'uri': self._TEST_URI}, HTTP_HOST=self.http_host)
        self.assertEqual(response.status_code, 404)

    @mock.patch('humfrey.desc.views.DocView.get_types')
    @mock.patch('humfrey.desc.views.DocView.endpoint')
    @mock.patch('humfrey.linkeddata.views.MappingView.id_mapping', TEST_ID_MAPPING)
    def testUnicodeURLs(self, endpoint, get_types):
        get_types.return_value = (rdflib.URIRef('http://example.org/vocab/Thing'),)

        graph = rdflib.ConjunctiveGraph()
        graph.add((rdflib.URIRef(self._TEST_URI), RDF.type, rdflib.URIRef('http://example.org/vocab/Thing')))
        endpoint.query.return_value = graph

        url_tests = [
            # Test that percent-encoded URLs get decoded as UTF-8
            ('/doc/fu%C3%9F', 'http://id.example.org/fuß', False),
        ]

        for url, uri, redirect in url_tests:
            response = self.client.get(url, HTTP_HOST=self.http_host)
            self.assertEqual(response.status_code, 301 if redirect else 200)
            if redirect:
                self.assertEqual(response['Location'], uri)
            else:
                self.assertEqual(response.context['subject_uri'], rdflib.URIRef(uri))
