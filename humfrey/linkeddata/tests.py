import mock
import unittest2
import rdflib

from django.conf import settings
from django.core.handlers.base import BaseHandler
from django_hosts.reverse import reverse_crossdomain

from humfrey.linkeddata.uri import doc_forward, doc_backward

TEST_ID_MAPPING = (
    ('http://random.example.org/id/', 'http://data.example.org/doc:random/', False),
    ('http://id.example.org/', 'http://data.example.org/doc/', True)
)

@mock.patch('django.conf.settings.ID_MAPPING', TEST_ID_MAPPING)
class URITestCase(unittest2.TestCase):
    def testDocLocal(self):
        uri = rdflib.URIRef('http://id.example.org/foo')
        self.assertEqual(doc_forward(uri, format='n3'),
                         'http://data.example.org/doc/foo.n3')

        uri = rdflib.URIRef('http://random.example.org/id/foo')
        self.assertEqual(doc_forward(uri),
                         'http://data.example.org/doc:random/foo')
    
    def testDocRemote(self):
        uri = rdflib.URIRef('http://remote.example.org/foo')
        doc_root = 'http:' + reverse_crossdomain('data', 'doc-generic')
        desc_root = 'http:' + reverse_crossdomain('data', 'desc')
        qs_with_format = '?uri=http%3A%2F%2Fremote.example.org%2Ffoo&format=nt'
        qs_without_format = '?uri=http%3A%2F%2Fremote.example.org%2Ffoo'
        
        # With no indication as to whether we know about it
        self.assertEqual(doc_forward(uri),
                         desc_root + qs_without_format)
        self.assertEqual(doc_forward(uri, format='nt'),
                         desc_root + qs_with_format)

        # When we provide a graph that doesn't mention it
        graph = rdflib.ConjunctiveGraph()
        self.assertEqual(doc_forward(uri, graph=graph),
                         desc_root + qs_without_format)
        self.assertEqual(doc_forward(uri, graph=graph, format='nt'),
                         desc_root + qs_with_format)

        # Now our graph knows something about it
        graph.add((uri, rdflib.URIRef('http://example.org/predicate'), rdflib.Literal('foo')))
        self.assertEqual(doc_forward(uri, graph=graph),
                         doc_root + qs_without_format)
        self.assertEqual(doc_forward(uri, graph=graph, format='nt'),
                         doc_root + qs_with_format)

        # When we definitely know nothing about it, go straight off-site
        self.assertEqual(doc_forward(uri, described=False), uri)
        self.assertEqual(doc_forward(uri, described=False, format='nt'), uri)

        # When we definitely know something about it, go straight off-site
        self.assertEqual(doc_forward(uri, described=True),
                         doc_root + qs_without_format)
        self.assertEqual(doc_forward(uri, described=True, format='nt'),
                         doc_root + qs_with_format)

    def testDocLocalNegotiate(self):
        request = mock.Mock()
        request.META = mock.MagicMock()
        request.META.__getitem__.return_value = 'application/rdf+xml'
        
        uri = rdflib.URIRef('http://id.example.org/foo')
        self.assertEqual(doc_forward(uri, request=request),
                         'http://data.example.org/doc/foo.rdf')

        request.META.__getitem__.assert_called_once_with('HTTP_ACCEPT')
        
    def testDocLocalNegotiateMissing(self):
        request = mock.Mock()
        request.META = mock.MagicMock()
        request.META.__getitem__.return_value = 'unknown/imt'
        
        uri = rdflib.URIRef('http://id.example.org/foo')
        self.assertEqual(doc_forward(uri, request=request),
                         'http://data.example.org/doc/foo')

        request.META.__getitem__.assert_called_once_with('HTTP_ACCEPT')
        

class EndpointViewTestCase(unittest2.TestCase):
    pass

class IdViewTestCase(unittest2.TestCase):
    pass

class DescViewTestCase(unittest2.TestCase):
    pass

class DocViewTestCase(unittest2.TestCase):
    pass




#    def testDoc

        
if __name__ == '__main__':
    unittest2.main()