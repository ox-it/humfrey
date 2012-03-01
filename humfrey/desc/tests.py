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

from humfrey.desc import rdf_processors, views
from humfrey.utils import sparql, resource
from humfrey.tests.stubs import patch_id_mapping

class GraphTestMixin(object):
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

    @patch_id_mapping
    def testAll(self):
        for rdf_processor in self._ALL:
            endpoint = mock.Mock(spec=sparql.Endpoint)
            graph = rdflib.ConjunctiveGraph()
            doc_uri = rdflib.URIRef('http://example.org/doc/Foo')
            subject_uri = rdflib.URIRef('http://example.org/id/Foo')
            subject = resource.Resource(subject_uri, graph, endpoint)

            doc_view = views.DocView.as_view()
            renderers = doc_view._renderers

            request = self.factory.get('')

            context = rdf_processor(request=request,
                                    graph=graph,
                                    doc_uri=doc_uri,
                                    subject_uri=subject_uri,
                                    subject=subject,
                                    endpoint=endpoint,
                                    renderers=renderers)

            self.assertFalse(endpoint.query.called, "The RDF processor should not be touching the endpoint (at the moment)")
            self.check_valid_terms(graph)
            self.assertIsInstance(context, (type(None), dict))

#@mock.patch('humfrey.linkeddata.uri.reverse_full', stub_reverse_full)
class DocViewTestCase(ClientTestCase, GraphTestMixin):
    _TEST_URI = 'http://data.example.org/id/foo'
    _HTTP_HOST = 'data.example.org'

    @mock.patch('humfrey.desc.views.DocView.get_types')
    @mock.patch('humfrey.desc.views.DocView.endpoint')
    def testGraphValid(self, endpoint, get_types):
        get_types.return_value = (rdflib.URIRef('http://example.org/vocab/Thing'),)
        endpoint.query.return_value = rdflib.ConjunctiveGraph()
        response = self.client.get('/doc/', {'uri': self._TEST_URI}, HTTP_HOST=self._HTTP_HOST)
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['subject_uri'], rdflib.URIRef)
        self.assertIsInstance(response.context['doc_uri'], rdflib.URIRef)
        self.check_valid_terms(response.context['graph'])

    @mock.patch('humfrey.desc.views.DocView.get_types')
    def testNoTypes(self, get_types):
        get_types.return_value = ()
        response = self.client.get('/doc/', {'uri': self._TEST_URI}, HTTP_HOST=self._HTTP_HOST)
        self.assertEqual(response.status_code, 404)

    @mock.patch('humfrey.desc.views.DocView.get_types')
    @mock.patch('humfrey.desc.views.DocView.endpoint')
    @patch_id_mapping
    def testUnicodeURLs(self, endpoint, get_types):
        get_types.return_value = (rdflib.URIRef('http://example.org/vocab/Thing'),)

        graph = rdflib.ConjunctiveGraph()
        graph.add((rdflib.URIRef(self._TEST_URI), RDF.type, rdflib.URIRef('http://example.org/vocab/Thing')))
        endpoint.query.return_value = graph

        url_tests = [
            ('/doc/fu%C3%9F', u'http://id.example.org/fuß', False),
            ('/doc/fu%c3%9F', '/doc/fu%C3%9F', True),
        ]

        for url, uri, redirect in url_tests:
            print '='*80
            print 'TESTING', url, uri, redirect
            import urlparse
            print "GP", repr(self.client._get_path(urlparse.urlparse(url)))
            response = self.client.get(url, HTTP_HOST=self._HTTP_HOST)
            self.assertEqual(response.status_code, 301 if redirect else 200)
            if redirect:
                self.assertEqual(response['Location'], uri)
            else:
                self.assertEqual(response.context['subject_uri'], rdflib.URIRef(uri))
