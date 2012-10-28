import unittest

import rdflib
import mock

from humfrey.utils.namespaces import HUMFREY, NS
from humfrey.update.transform.normalize import NotationNormalization

RDF = NS.rdf
SKOS = NS.skos

class NotationNormalizationTestCase(unittest.TestCase):
    parent_node = rdflib.URIRef('http://example.com/parent')
    child_node = rdflib.URIRef('http://example.com/child')
    other_node = rdflib.URIRef('http://example.com/other')
    original_node = rdflib.URIRef('http://example.com/original')
    target_node = rdflib.URIRef('http://example.com/target')
    test_datatype = rdflib.URIRef('http://example.com/notation')
    test_notation = rdflib.Literal('foo', datatype=test_datatype)

    triples = [
        (parent_node, SKOS.narrower, original_node),
        (original_node, RDF.type, SKOS.Concept),
        (original_node, SKOS.narrower, child_node),
        (original_node, SKOS.notation, test_notation),
        (original_node, SKOS.broader, other_node),
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

        self.assertIn((self.parent_node, SKOS.narrower, self.original_node), graph)
        self.assertIn((self.original_node, SKOS.narrower, self.child_node), graph)
        self.assertIn((self.original_node, HUMFREY.noIndex, rdflib.Literal(True)), graph)
        self.assertNotIn((self.original_node, SKOS.notation, self.test_notation), graph)
        self.assertIn((self.original_node, SKOS.broader, self.other_node), graph)

    def testFound(self):
        normalization = NotationNormalization(datatypes=(self.test_datatype,))
        normalization.endpoint = mock.Mock()
        normalization.endpoint.query.return_value = ((self.test_notation, self.target_node),)

        graph = self.run_normalization(normalization, self.triples)

        self.assertIn((self.parent_node, SKOS.narrower, self.target_node), graph)
        self.assertNotIn((self.original_node, SKOS.narrower, self.child_node), graph)
        self.assertNotIn((self.original_node, HUMFREY.noIndex, rdflib.Literal(True)), graph)
        self.assertNotIn((self.original_node, SKOS.notation, self.test_notation), graph)
        self.assertNotIn((self.original_node, SKOS.broader, self.other_node), graph)

    def testFoundWithSafe(self):
        normalization = NotationNormalization(datatypes=(self.test_datatype,),
                                              safe_predicates=(SKOS.broader,))
        normalization.endpoint = mock.Mock()
        normalization.endpoint.query.return_value = ((self.test_notation, self.target_node),)

        graph = self.run_normalization(normalization, self.triples)
        
        self.assertIn((self.target_node, SKOS.broader, self.other_node), graph)
