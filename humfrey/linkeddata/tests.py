# *-* coding: UTF-8 *-*

import functools
import mock
import unittest2
import rdflib

from django.core.urlresolvers import set_urlconf
from django_hosts.reverse import get_host

from humfrey.linkeddata import mappingconf, resource
from humfrey.linkeddata.uri import doc_forward, doc_backward
from humfrey.tests.stubs import patch_id_mapping

TEST_ID_MAPPING = (
    ('http://random.example.org/id/', 'http://data.example.org/doc:random/', False),
    ('http://id.example.org/', 'http://data.example.org/doc/', True)
)


def set_mappingconf(func):
    @functools.wraps(func)
    def f(*args, **kwargs):
        mappingconf.set_desc_view(('data', 'desc'))
        mappingconf.set_doc_view(('data', 'doc-generic'))
        mappingconf.set_id_mapping(TEST_ID_MAPPING)
        mappingconf.set_resource_registry(resource.base_resource_registry)
        try:
            return func(*args, **kwargs)
        finally:
            mappingconf.set_desc_view(None)
            mappingconf.set_doc_view(None)
            mappingconf.set_id_mapping(None)
            mappingconf.set_resource_registry(None)
    return f


class URITestCase(unittest2.TestCase):
    def setUp(self):
        set_urlconf(get_host('data').urlconf)

    @set_mappingconf
    def testDocLocal(self):
        uri = rdflib.URIRef('http://id.example.org/foo')
        self.assertEqual(doc_forward(uri, format='n3'),
                         'http://data.example.org/doc/foo.n3')

        uri = rdflib.URIRef('http://random.example.org/id/foo')
        self.assertEqual(doc_forward(uri),
                         'http://data.example.org/doc:random/foo')

    @set_mappingconf
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

    @set_mappingconf
    def testDocLocalNegotiate(self):
        uri = rdflib.URIRef('http://id.example.org/foo')
        self.assertEqual(doc_forward(uri),
                         'http://data.example.org/doc/foo')

    @set_mappingconf
    def testDocLocalNegotiateMissing(self):
        uri = rdflib.URIRef('http://id.example.org/foo')
        self.assertEqual(doc_forward(uri),
                         'http://data.example.org/doc/foo')

class UnicodeURITestCase(unittest2.TestCase):
    TESTS = [
        (u'http://id.example.org/fuß', 'http://data.example.org/doc/fu%C3%9F'),
        (u'http://id.example.org/βήτα', 'http://data.example.org/doc/%CE%B2%CE%AE%CF%84%CE%B1'),
        (u'http://id.other.org/fuß', 'http://data.example.org/doc/?uri=http%3A%2F%2Fid.other.org%2Ffu%C3%9F'),
        (u'http://id.other.org/βήτα', 'http://data.example.org/doc/?uri=http%3A%2F%2Fid.other.org%2F%CE%B2%CE%AE%CF%84%CE%B1'),

        # Requests with percent-encoded UTF-8 bytes
        ('http://id.example.org/fu%C3%9F', 'http://data.example.org/doc/fu%C3%9F'),
        ('http://id.example.org/%CE%B2%CE%AE%CF%84%CE%B1', 'http://data.example.org/doc/%CE%B2%CE%AE%CF%84%CE%B1'),
        ('http://id.other.org/fu%C3%9F', 'http://data.example.org/doc/?uri=http%3A%2F%2Fid.other.org%2Ffu%C3%9F'),
        ('http://id.other.org/%CE%B2%CE%AE%CF%84%CE%B1', 'http://data.example.org/doc/?uri=http%3A%2F%2Fid.other.org%2F%CE%B2%CE%AE%CF%84%CE%B1'),

        # Requests without percent-encoding UTF-8 bytes
        ('http://id.example.org/fu\xc3\x9f', 'http://data.example.org/doc/fu%C3%9F'),
        ('http://id.example.org/\xce\xb2\xce\xae\xcf\x84\xce\xb1', 'http://data.example.org/doc/%CE%B2%CE%AE%CF%84%CE%B1'),
    ]

    def setUp(self):
        set_urlconf(get_host('data').urlconf)

    @set_mappingconf
    def testUnicodeForward(self):
        for uri, url in self.TESTS:
            self.assertEqual(doc_forward(uri, described=True), url)

    @set_mappingconf
    def testUnicodeBackward(self):
        for uri, url in self.TESTS:
            if isinstance(uri, unicode):
                self.assertEqual(doc_backward(url)[0], rdflib.URIRef(uri))


if __name__ == '__main__':
    unittest2.main()
