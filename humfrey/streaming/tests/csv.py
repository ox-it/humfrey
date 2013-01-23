from __future__ import absolute_import

import csv
import StringIO
import unittest

from .. import CSVSerializer
from .data import TEST_RESULTSET

class CSVRendererTestCase(unittest.TestCase):
    def testValidCSVResultSet(self):
        data = ''.join(CSVSerializer(TEST_RESULTSET))

        try:
            data = csv.reader(StringIO.StringIO(data))
        except Exception, e:
            raise AssertionError(e)

        # Pop the columns and make sure they match.
        columns = data.next()
        self.assertEqual(columns, list(TEST_RESULTSET.fields))

        for result, target_result in zip(data, TEST_RESULTSET):
            for term, target_term in zip(result, target_result):
                term = term.decode('utf-8')
                if target_term is None:
                    self.assertEqual(term, '')
                else:
                    self.assertEqual(term, unicode(target_term))

    def testValidCSVBoolean(self):
        for value in (True, False):
            data = ''.join(CSVSerializer(value))
            self.assertEqual(data, 'true\n' if value else 'false\n')
