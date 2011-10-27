import mock
import unittest2
import rdflib

from humfrey.linkeddata.uri import doc_forward
from humfrey.tests.stubs import stub_reverse_full

TEST_ID_MAPPING = (
    ('http://random.example.org/id/', 'http://data.example.org/doc:random/', False),
    ('http://id.example.org/', 'http://data.example.org/doc/', True)
)

@mock.patch('django.conf.settings.ID_MAPPING', TEST_ID_MAPPING)
@mock.patch('humfrey.linkeddata.uri.reverse_full', stub_reverse_full)
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
        doc_root = 'http://data.example.org/doc/'
        desc_root = 'http://data.example.org/desc/'
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
        self.assertEqual(doc_forward(uri, described=False), unicode(uri))
        self.assertEqual(doc_forward(uri, described=False, format='nt'), unicode(uri))

        # When we definitely know something about it, go straight off-site
        self.assertEqual(doc_forward(uri, described=True),
                         doc_root + qs_without_format)
        self.assertEqual(doc_forward(uri, described=True, format='nt'),
                         doc_root + qs_with_format)

    def testDocLocalNegotiate(self):
        uri = rdflib.URIRef('http://id.example.org/foo')
        self.assertEqual(doc_forward(uri),
                         'http://data.example.org/doc/foo')

    def testDocLocalNegotiateMissing(self):
        uri = rdflib.URIRef('http://id.example.org/foo')
        self.assertEqual(doc_forward(uri),
                         'http://data.example.org/doc/foo')

if __name__ == '__main__':
    unittest2.main()
