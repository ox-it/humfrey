# -*- coding: utf-8
import datetime
import decimal
import itertools
import os

import unittest2

import humfrey.tests
from humfrey.update.transform.spreadsheet import ODSToTEI, GnumericToTEI, Currency, Percentage

EXPECTED = [{'name': 'Sheet1',
             'data': [['Column A', 'Column B', 'Column C', 'Column D', 'Column E'],
                      ['This', 'is', 'a', 'simple', 'row'],
                      ['This', '', 'has', '', 'gaps'],
                      ['Larger', '', '', '', 'gaps'],
                      [],
                      [],
                      ['Some', 'missing', 'rows', 'just', 'above'],
                      ['A date', '', '', '', datetime.date(2011, 1, 1)],
                      ['A date and time', '', '', '', datetime.datetime(2011, 1, 1, 12, 34, 56)],
                      ['A natural number', '', '', '', 12345],
                      ['A decimal value', '', '', '', 12345.6789],
                      ['A percentage', '', '', '', Percentage('0.45', '45.00%')],
                      ['A currency value', '', '', '', Currency('12.34', 'GBP', '£12.34')],
                      [], [], [], [], [], [], [], [], [], [], [], [], [],
                      ['']*7 + ['All by itself']]},
            {'name': 'Sheet2',
             'data': [['Something on the second sheet']]},
            {'name': 'Sheet3',
             'data': []}
]

class SpreadsheetTestCase(unittest2.TestCase):
    DATA_DIRECTORY = os.path.join(os.path.dirname(humfrey.tests.__file__),
                                  'data', 'spreadsheet')

    def checkData(self, sheets):
        for s, (sheet, expected) in enumerate(itertools.zip_longest(sheets, EXPECTED)):
            self.assertTrue(sheet is not None, "Missing sheet")
            self.assertTrue(expected is not None, "Sheet missing")
            self.assertEqual(sheet.name, expected['name'], 'Unexpected sheet name')

            for i, (row, expected_row) in enumerate(itertools.zip_longest(sheet.rows, expected['data'])):
                self.assertTrue(row is not None, "Missing row (%d:%d)" % (s + 1, i + 1))
                if expected_row is None:
                    self.assertTrue(not any(row.cells), 'Row was supposed to be empty (%d)' % (i + 1))
                    continue

                for j, (cell, expected_cell) in enumerate(itertools.zip_longest(row.cells, expected_row)):
                    self.assertTrue(cell is not None, "Missing cell (%d:%d:%d)" % (s + 1, i + 1, j + 1))
                    if expected_cell is None:
                        self.assertTrue(not cell, "Cell was supposed to be empty (%d:%d:%d)" % (s + 1, i + 1, j + 1))
                        continue
                    if isinstance(expected_cell, decimal.Decimal):
                        self.assertAlmostEqual(float(cell), float(expected_cell), 5, "Decimals didn't match")
                    else:
                        self.assertEqual(cell, expected_cell, "Cell had unexpected contents (%d:%d:%d)" % (s + 1, i + 1, j + 1))

class OpenDocumentSpreadsheetTestCase(SpreadsheetTestCase):
    INPUT_FILENAME = os.path.join(SpreadsheetTestCase.DATA_DIRECTORY, 'opendocument.ods')

    def testOpenDocumentSpreadsheet(self):
        transform = ODSToTEI()
        self.checkData(transform.sheets(self.INPUT_FILENAME))

class GnumericSpreadsheetTestCase(SpreadsheetTestCase):
    INPUT_FILENAME = os.path.join(SpreadsheetTestCase.DATA_DIRECTORY, 'gnumeric.gnumeric')

    def testOpenDocumentSpreadsheet(self):
        transform = GnumericToTEI()
        self.checkData(transform.sheets(self.INPUT_FILENAME))



if __name__ == '__main__':
    unittest2.main()
