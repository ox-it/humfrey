try:
    import json
except ImportError:
    import simplejson as json

import collections
import csv
import imp
import itertools
import os
import StringIO

import unittest2
import rdflib

from humfrey.results.views import standard as standard_views
from humfrey.utils import sparql, namespaces

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

class SRJRendererTestCase(unittest2.TestCase):

    def testValidSRJResultSet(self):
        data = standard_views.ResultSetView()._spool_srj_resultset(TEST_RESULTSET)
        data = ''.join(data)

        target_data_filename = os.path.join(imp.find_module('humfrey')[1], 'tests', 'data', 'linkeddata', 'srj_resultset.json')
        with open(target_data_filename, 'rb') as json_file:
            target_data = json.load(json_file)

        try:
            data = json.loads(data)
        except Exception, e:
            raise AssertionError(e)

        # Rename bnodes in the order they appear. Otherwise we're comparing
        # arbitrary strings that actually mean the same thing.
        for results in (data['results']['bindings'], target_data['results']['bindings']):
            i, mapping = 0, {}
            for result in results:
                result = sorted(result.iteritems())
                for _, value in result:
                    if value['type'] == 'bnode':
                        if value['value'] in mapping:
                            value['value'] = mapping[value['value']]
                        else:
                            value['value'] = mapping[value['value']] = i
                            i += 1

        self.assertEqual(data['head']['vars'], target_data['head']['vars'])
        self.assertEqual(data['results'], target_data['results'])

    def testValidSRJBoolean(self):
        for value in (True, False):
            data = standard_views.ResultSetView()._spool_srj_boolean(value)
            data = ''.join(data)
            try:
                data = json.loads(data)
            except Exception, e:
                raise AssertionError(e)
            self.assertEqual(data, {'head': {}, 'boolean': value})


class CSVRendererTestCase(unittest2.TestCase):
    def testValidCSVResultSet(self):
        data = standard_views.ResultSetView()._spool_csv_resultset(TEST_RESULTSET)
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
            data = standard_views.ResultSetView()._spool_csv_boolean(value)
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