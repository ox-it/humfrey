import itertools
import os

from django.utils import unittest

import rdflib

from humfrey.utils import namespaces
from humfrey.sparql.results import Result, SparqlResultList
from . import srx, encoding

_TEST_BNODE = rdflib.BNode()
TEST_RESULTSET_CLASS = Result(('one', 'two'))

TEST_RESULTSET = SparqlResultList(
    ('one', 'two'),
    map(TEST_RESULTSET_CLASS, [
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
]))

class ParserTestCase(unittest.TestCase):
    def testSRXIterative(self):
        import humfrey.tests
        filename = os.path.join(os.path.dirname(humfrey.tests.__file__),
                                'data', 'linkeddata', 'xml_resultset.xml')

        def map_binding(b, d):
            if isinstance(b, rdflib.BNode):
                try:
                    return d[b]
                except KeyError:
                    d[b] = len(d)
                    return d[b]
            return b
        def map_result(r, d):
            return Result(r._fields, (map_binding(b, d) for b in r))

        actual_mapping, expected_mapping = {}, {}

        f = open(filename, 'r')
        results = srx.SRXSource(f, 'UTF-8')
        try:
            self.assertIsInstance(results, SparqlResultSet)
            for actual, expected in itertools.izip_longest(results, TEST_RESULTSET):
                actual, expected = map_result(actual, actual_mapping), map_result(expected, expected_mapping)
                self.assertEqual(actual, expected)
        finally:
            for result in results: pass
            f.close()

class CoercingIRIsTestCase(unittest.TestCase):
    bad_characters = u'^<>"{}|^`\\' + ''.join(unichr(i) for i in range(0, 33))

    def testBadCharacters(self):
        for char in self.bad_characters:
            original_iri = rdflib.URIRef(u'http://example.com/foo' + char + 'baz')
            expected_iri = rdflib.URIRef(u'http://example.com/foo%%%02Xbaz' % ord(char))

            triples = [(original_iri, original_iri, rdflib.Literal('foo'))]
            triples = list(encoding.coerce_triple_iris(triples))

            for iri in triples[0][:2]:
                self.assertEqual(iri, expected_iri)

    def testGoodCharacters(self):
        original_iri = rdflib.URIRef(u'http://example.com/' + u''.join(unichr(i) for i in range(0, 1024) if unichr(i) not in self.bad_characters))

        triples = [(original_iri, original_iri, rdflib.Literal('foo'))]
        triples = list(encoding.coerce_triple_iris(triples))

        for iri in triples[0][:2]:
            self.assertEqual(iri, original_iri)
