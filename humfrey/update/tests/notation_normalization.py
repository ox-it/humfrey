# *-* coding: UTF-8

import unittest

import rdflib
import mock
import tempfile

from humfrey.streaming import parse, serialize
from humfrey.utils.namespaces import HUMFREY, NS
from humfrey.update.transform.normalize import NotationNormalization

RDF = NS.rdf
SKOS = NS.skos

class NotationNormalizationTestCase(unittest.TestCase):
    parent_node = rdflib.URIRef('http://example.com/parent')
    child_node = rdflib.URIRef('http://example.com/child')
    other_node = rdflib.URIRef('http://example.com/other')

    # URIRef→URIRef, BNode→URIRef, BNode→BNode
    original_nodes = (rdflib.URIRef('http://example.com/original'),
                      rdflib.BNode(),
                      rdflib.BNode())
    target_nodes = (rdflib.URIRef('http://example.com/target'),
                    rdflib.URIRef('http://example.com/target'),
                    rdflib.BNode())
    test_datatype = rdflib.URIRef('http://example.com/notation')
    test_notation = rdflib.Literal('foo', datatype=test_datatype)

    def setUp(self):
        self.triple_sets = [(original_node, target_node, [
            (self.parent_node, SKOS.narrower, original_node),
            (original_node, RDF.type, SKOS.Concept),
            (original_node, SKOS.narrower, self.child_node),
            (original_node, SKOS.notation, self.test_notation),
            (original_node, SKOS.broader, self.other_node),
            (self.other_node, SKOS.prefLabel, rdflib.Literal("Title")),
        ]) for original_node, target_node in zip(self.original_nodes, self.target_nodes)]

    def run_normalization(self, normalization, triples):
        try:
            in_file, out_file = [tempfile.NamedTemporaryFile(suffix='.rdf') for i in range(2)]
            serialize(triples, in_file)

            while not normalization.done:
                in_file.seek(0)
                out_file.seek(0)
                pipeline = normalization(parse(in_file).get_triples())
                serialize(pipeline, out_file)
                out_file.truncate()
                in_file, out_file = out_file, tempfile.NamedTemporaryFile(suffix='.rdf', delete=False)

            in_file.seek(0)

            graph = rdflib.ConjunctiveGraph()
            graph.parse(in_file, preserve_bnode_ids=True)
            return graph
        finally:
            in_file.close()
            out_file.close()


    def testNotFound(self):
        for original_node, target_node, triples in self.triple_sets:
            normalization = NotationNormalization(datatypes=(self.test_datatype,))
            normalization.endpoint = mock.Mock()
            normalization.endpoint.query.return_value = ()

            graph = self.run_normalization(normalization, triples)

            self.assertIn((self.parent_node, SKOS.narrower, original_node), graph)
            self.assertIn((original_node, SKOS.narrower, self.child_node), graph)
            self.assertIn((original_node, HUMFREY.noIndex, rdflib.Literal(True)), graph)
            self.assertNotIn((original_node, SKOS.notation, self.test_notation), graph)
            self.assertIn((original_node, SKOS.broader, self.other_node), graph)
            self.assertIn((self.other_node, SKOS.prefLabel, rdflib.Literal("Title")), graph)

    def testFound(self):
        for original_node, target_node, triples in self.triple_sets:
            normalization = NotationNormalization(datatypes=(self.test_datatype,))
            normalization.endpoint = mock.Mock()
            normalization.endpoint.query.return_value = ((self.test_notation, target_node),)

            graph = self.run_normalization(normalization, triples)

            self.assertIn((self.parent_node, SKOS.narrower, target_node), graph)
            for node in (original_node, target_node):
                self.assertNotIn((node, SKOS.narrower, self.child_node), graph)
                self.assertNotIn((node, HUMFREY.noIndex, rdflib.Literal(True)), graph)
                self.assertNotIn((node, SKOS.notation, self.test_notation), graph)
                self.assertNotIn((node, SKOS.broader, self.other_node), graph)
            self.assertIn((self.other_node, SKOS.prefLabel, rdflib.Literal("Title")), graph)

    def testFoundWithSafe(self):
        for original_node, target_node, triples in self.triple_sets:
            normalization = NotationNormalization(datatypes=(self.test_datatype,),
                                              safe_predicates=(SKOS.broader,))
            normalization.endpoint = mock.Mock()
            normalization.endpoint.query.return_value = ((self.test_notation, target_node),)

            graph = self.run_normalization(normalization, triples)

            self.assertIn((target_node, SKOS.broader, self.other_node), graph)
            self.assertIn((self.other_node, SKOS.prefLabel, rdflib.Literal("Title")), graph)
