import collections
import csv
import imp
import itertools
import os
import StringIO

import mock
import unittest2
import rdflib
import simplejson

from django.conf import settings
from django.core.handlers.base import BaseHandler

from humfrey.linkeddata import views
from humfrey.linkeddata.uri import doc_forward, doc_backward
from humfrey.tests.stubs import stub_reverse_crossdomain
from humfrey.utils import sparql, namespaces

TEST_ID_MAPPING = (
    ('http://random.example.org/id/', 'http://data.example.org/doc:random/', False),
    ('http://id.example.org/', 'http://data.example.org/doc/', True)
)

_TEST_BNODE = rdflib.BNode()
TEST_RESULTSET_RESULT = collections.namedtuple('Result', 'one two')
TEST_RESULTSET = sparql.ResultList(list(itertools.starmap(TEST_RESULTSET_RESULT, [
    (rdflib.URIRef('http://example.org/one'), _TEST_BNODE),
    (rdflib.Literal('hello'), rdflib.Literal('hello', lang='en')),
    (rdflib.Literal('foo"bar'), rdflib.Literal('foo\nbar')),
    (rdflib.Literal('foo,bar'), rdflib.Literal('foo;bar')),
    (rdflib.Literal('foo bar'), rdflib.Literal('foo\tbar')),
    (rdflib.Literal(1), rdflib.Literal('2011-01-02T12:34:56Z', datatype=namespaces.NS.xsd.timeDate)),
    (None, None),
    (_TEST_BNODE, rdflib.BNode()),
    (rdflib.URIRef('http://example.org/'), rdflib.URIRef('mailto:alice@example.org')),
    (rdflib.URIRef('urn:isbn:9781449306595'), rdflib.URIRef('tag:bob@example.org,2011:foo')),
])))
del _TEST_BNODE
TEST_RESULTSET.fields = ('one', 'two')
TEST_RESULTSET.query = 'The query that was run'
TEST_RESULTSET.duration = 1



@mock.patch('django.conf.settings.ID_MAPPING', TEST_ID_MAPPING)
@mock.patch('humfrey.linkeddata.uri.reverse_crossdomain', stub_reverse_crossdomain)
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

class SRJRendererTestCase(unittest2.TestCase):

    def testValidSRJResultSet(self):
        data = views.ResultSetView()._spool_srj_resultset(TEST_RESULTSET)
        data = ''.join(data)

        target_data_filename = os.path.join(imp.find_module('humfrey')[1], 'tests', 'data', 'linkeddata', 'srj_resultset.json')
        with open(target_data_filename, 'rb') as f:
            target_data = simplejson.load(f)

        try:
            data = simplejson.loads(data)
        except Exception, e:
            raise AssertionError(e)

        # Rename bnodes in the order they appear. Otherwise we're comparing
        # arbitrary strings that actually mean the same thing.
        for results in (data['results'], target_data['results']):
            i, mapping = 0, {}
            for result in results:
                result = sorted(result.iteritems())
                for k, v in result:
                    if v['type'] == 'bnode':
                        if v['value'] in mapping:
                            v['value'] = mapping[v['value']]
                        else: 
                            v['value'] = mapping[v['value']] = i
                            i += 1

        self.assertEqual(data['head']['vars'], target_data['head']['vars'])
        self.assertEqual(data['results'], target_data['results'])

    def testValidSRJBoolean(self):
        for value in (True, False):
            data = views.ResultSetView()._spool_srj_boolean(value)
            data = ''.join(data)
            try:
                data = simplejson.loads(data)
            except Exception, e:
                raise AssertionError(e)
            self.assertEqual(data, {'head': {}, 'boolean': value})


class CSVRendererTestCase(unittest2.TestCase):
    def testValidCSVResultSet(self):
        data = views.ResultSetView()._spool_csv_resultset(TEST_RESULTSET)
        data = ''.join(data)

        try:
            data = csv.reader(StringIO.StringIO(data))
        except Exception, e:
            raise AssertionError(e)

        for result, target_result in zip(data, TEST_RESULTSET):
            for term, target_term in zip(result, target_result):
                term = term.decode('utf-8')
                if target_term is None:
                    self.assertEqual(term, '')
                else:
                    self.assertEqual(term, unicode(target_term))

    def testValidCSVBoolean(self):
        for value in (True, False):
            data = views.ResultSetView()._spool_csv_boolean(value)
            data = ''.join(data)
            self.assertEqual(data, 'true\n' if value else 'false\n')

class EndpointViewTestCase(unittest2.TestCase):
    pass

class IdViewTestCase(unittest2.TestCase):
    pass

class DescViewTestCase(unittest2.TestCase):
    pass

class DocViewTestCase(unittest2.TestCase):
    pass

if __name__ == '__main__':
    unittest2.main()
