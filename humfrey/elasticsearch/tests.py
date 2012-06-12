import copy
import mock
import unittest

import rdflib

from humfrey.sparql.results import SparqlResultList, Result

from . import update

class ResultsParserTestCase(unittest.TestCase):
    TEST_FIELDS = """uri label altLabel ship_label
                     ship_class occupies_label""".split()
    TEST_URI_A = rdflib.URIRef('http://example.org/id/malcolm')
    TEST_URI_B = rdflib.URIRef('http://example.org/id/niska')
    TEST_RESULTS = SparqlResultList(TEST_FIELDS, [
        Result(TEST_FIELDS, {'uri': TEST_URI_A,
                             'label': 'Malcolm Reynolds'}),
        Result(TEST_FIELDS, {'uri': TEST_URI_A,
                             'altLabel': 'Mal'}),
        Result(TEST_FIELDS, {'uri': TEST_URI_A,
                             'altLabel': "Cap'n"}),
        Result(TEST_FIELDS, {'uri': TEST_URI_A,
                             'ship_label': 'Serenity',
                             'ship_class': 'Firefly'}),
        Result(TEST_FIELDS, {'uri': TEST_URI_A,
                             'appearance_number': 'S01E01',
                             'appearance_label': 'Serenity'}),
        Result(TEST_FIELDS, {'uri': TEST_URI_A,
                             'appearance_number': 'S01E02',
                             'appearance_label': 'The Train Job'}),
        Result(TEST_FIELDS, {'uri': TEST_URI_B,
                             'label': 'Adelei Niska'}),
        Result(TEST_FIELDS, {'uri': TEST_URI_B,
                             'altLabel': 'Niska'}),
        Result(TEST_FIELDS, {'uri': TEST_URI_B,
                             'appearance_number': 'S01E02',
                             'appearance_label': 'The Train Job'}),
        Result(TEST_FIELDS, {'uri': TEST_URI_B,
                             'appearance_number': 'S01E10',
                             'appearance_label': 'War Stories'})])
    TEST_META = type('', (), {'groups': 'altLabel appearance'})()

    EXPECTED_RESULT = [{'uri': TEST_URI_A,
                       'label': 'Malcolm Reynolds',
                       'altLabel': ["Cap'n", 'Mal'],
                       'ship': {'label': 'Serenity',
                                'class': 'Firefly'},
                       'appearance': [{'number': 'S01E01',
                                       'label': 'Serenity'},
                                      {'number': 'S01E02',
                                        'label': 'The Train Job'}]},
                       {'uri': TEST_URI_B,
                        'label': 'Adelei Niska',
                        'altLabel': ['Niska'],
                        'appearance': [{'number': 'S01E02',
                                        'label': 'The Train Job'},
                                       {'number': 'S01E10',
                                        'label': 'War Stories'}]}]

    def testDictify(self):
        dictify = update.IndexUpdater.dictify

        groups = (('d',),)
        original = {'uri': 'foo',
                    'a': 1,
                    'b': 2,
                    'c_a': 3,
                    'c_b': 4,
                    'd_id': 'x',
                    'd_a': 'c'}
        expected = {'foo': {'uri': 'foo',
                            'a': 1,
                            'b': 2,
                            'c': {'a': 3,
                                  'b': 4},
                            'd': {'x': {'a': 'c'}}}}

        self.assertEqual(dictify(groups, original), expected)

    def testMergeResults(self):
        one = {'foo': {'a': 1,
                       'b': {'a': 2,
                             'b': 3},
                       'c': {'x': {'a': 4},
                             'y': {'a': 5}}}}
        two = {'foo': {'a': 11,
                       'c': {'y': {'a': 12}}}}
        expected = {'foo': {'a': 11,
                            'b': {'a': 2,
                                  'b': 3},
                            'c': {'x': {'a': 4},
                                  'y': {'a': 12}}}}
        groups = (('c',),)

        self.assertEqual(update.IndexUpdater.merge_dicts(groups, one, two), expected)

    def testResultParsing(self):
        index_updater = update.IndexUpdater()
        index_updater.client = None

        actual = list(index_updater.parse_results(self.TEST_META, self.TEST_RESULTS))
        expected = copy.deepcopy(self.EXPECTED_RESULT)

        def sort_recursive(value):
            if isinstance(value, list):
                for subvalue in value:
                    sort_recursive(subvalue)
                value.sort()
            elif isinstance(value, dict):
                for subvalue in value.itervalues():
                    sort_recursive(subvalue)

        sort_recursive(actual)
        sort_recursive(expected)

        self.assertEqual(actual, expected)


