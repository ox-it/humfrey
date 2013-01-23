import functools
import itertools

import rdflib

from humfrey.sparql.results import SparqlResultList, Result
from humfrey.utils.namespaces import NS

_TEST_BNODE = rdflib.BNode()
TEST_RESULTSET_FIELDS = ('one', 'two')
TEST_RESULTSET_RESULT = functools.partial(Result, TEST_RESULTSET_FIELDS)
TEST_RESULTSET = SparqlResultList(('one', 'two'), itertools.imap(TEST_RESULTSET_RESULT, [
    (rdflib.URIRef('http://example.org/one'), _TEST_BNODE),
    (rdflib.Literal('hello'), rdflib.Literal('hello', lang='en')),
    (rdflib.Literal('foo"bar'), rdflib.Literal('foo\nbar')),
    (rdflib.Literal('foo,bar'), rdflib.Literal('foo;bar')),
    (rdflib.Literal('foo bar'), rdflib.Literal('foo\tbar')),
    (rdflib.Literal(1), rdflib.Literal('2011-01-02T12:34:56Z', datatype=NS.xsd.timeDate)),
    (None, None),
    (_TEST_BNODE, rdflib.BNode()),
    (rdflib.URIRef('http://example.org/'), rdflib.URIRef('mailto:alice@example.org')),
    (rdflib.URIRef('urn:isbn:9781449306595'), rdflib.URIRef('tag:bob@example.org,2011:foo')),
]))
del _TEST_BNODE
TEST_RESULTSET.fields = ('one', 'two')
TEST_RESULTSET.query = 'The query that was run'
TEST_RESULTSET.duration = 1
