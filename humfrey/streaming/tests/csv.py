import csv
import io
import unittest

from .. import CSVSerializer
from .data import TEST_RESULTSET

class CSVRendererTestCase(unittest.TestCase):
    def testValidCSVResultSet(self):
        data = b''.join(CSVSerializer(TEST_RESULTSET))

        try:
            data = csv.reader(io.StringIO(data.decode()))
        except Exception as e:
            raise AssertionError(e)

        # Pop the columns and make sure they match.
        columns = next(data)
        self.assertEqual(columns, list(TEST_RESULTSET.fields))

        for result, target_result in zip(data, TEST_RESULTSET):
            for term, target_term in zip(result, target_result):
                if target_term is None:
                    self.assertEqual(term, '')
                else:
                    self.assertEqual(term, str(target_term))

    def testValidCSVBoolean(self):
        for value in (True, False):
            data = b''.join(CSVSerializer(value))
            self.assertEqual(data, b'true\n' if value else b'false\n')
