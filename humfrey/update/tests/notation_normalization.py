import unittest

import rdflib
import mock

from humfrey.utils.namespaces import HUMFREY, NS
from humfrey.update.transform.normalize import NotationNormalization

RDF = NS.rdf
SKOS = NS.skos

class NotationNormalizationTestCase(unittest.TestCase):
    original_node = rdflib.URIRef('http://example.com/foo')
    target_node = rdflib.URIRef('http://example.com/bar')
    test_datatype = rdflib.URIRef('http://example.com/notation')
    test_notation = rdflib.Literal('foo', datatype=test_datatype)

    triples = [
        (original_node, RDF.type, SKOS.Concept),
        (original_node, SKOS.notation, test_notation),
    ]

    def run_normalization(self, normalization, triples):
        while not normalization.done:
            triples = list(normalization(triples))

        graph = rdflib.ConjunctiveGraph()
        graph += triples
        return graph

    def testNotFound(self):
        normalization = NotationNormalization(datatypes=(self.test_datatype,))
        normalization.endpoint = mock.Mock()
        normalization.endpoint.query.return_value = ()

        graph = self.run_normalization(normalization, self.triples)

        self.assertIn((self.original_node, HUMFREY.noIndex, rdflib.Literal(True)), graph)
        self.assertNotIn((self.original_node, SKOS.notation, self.test_notation), graph)
