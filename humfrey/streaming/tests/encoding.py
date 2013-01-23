import unittest

import rdflib

from .. import encoding

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
