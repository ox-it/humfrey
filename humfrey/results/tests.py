try:
    import simplejson as json
except ImportError:
    import json

import collections
import csv
import imp
import itertools
import os
import StringIO

import unittest2
import rdflib

from humfrey.results.views import standard as standard_views
from humfrey.utils import namespaces
import humfrey.sparql.results


class CSVRendererTestCase(unittest2.TestCase):
    def testValidCSVResultSet(self):
        data = standard_views.ResultSetView()._spool_csv_resultset(TEST_RESULTSET)
        data = ''.join(data)

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
            data = standard_views.ResultSetView()._spool_csv_boolean(value)
            data = ''.join(data)
            self.assertEqual(data, 'true\n' if value else 'false\n')

class EndpointViewTestCase(unittest2.TestCase):
    pass

class IdViewTestCase(unittest2.TestCase):
    pass

class DescViewTestCase(unittest2.TestCase):
    pass

class DocViewTestCase(unittest2.TestCase):
    pass

if __name__ == '__main__':
    unittest2.main()
