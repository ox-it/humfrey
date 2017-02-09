import itertools
import os
import unittest

import rdflib

from humfrey.sparql.results import Result, SparqlResultList
from humfrey.utils.namespaces import NS

from .. import SRXParser
from .data import TEST_RESULTSET

class SRXParserTestCase(unittest.TestCase):
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

        f = open(filename, 'rb')
        results = SRXParser(f).get()
        try:
            self.assertIsInstance(results, SparqlResultList)
            for actual, expected in itertools.zip_longest(results, TEST_RESULTSET):
                actual, expected = map_result(actual, actual_mapping), map_result(expected, expected_mapping)
                self.assertEqual(actual, expected)
        finally:
            for result in results: pass
            f.close()
