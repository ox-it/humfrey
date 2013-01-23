import imp
import os
import unittest

from humfrey.utils import json

from .. import SRJSerializer
from .data import TEST_RESULTSET

class SRJRendererTestCase(unittest.TestCase):

    def testValidSRJResultSet(self):
        data = ''.join(SRJSerializer(TEST_RESULTSET))

        target_data_filename = os.path.join(imp.find_module('humfrey')[1], 'tests', 'data', 'linkeddata', 'srj_resultset.json')
        with open(target_data_filename, 'rb') as json_file:
            target_data = json.load(json_file)

        try:
            data = json.loads(data)
        except Exception, e:
            raise AssertionError(e)

        # Rename bnodes in the order they appear. Otherwise we're comparing
        # arbitrary strings that actually mean the same thing.
        for results in (data['results']['bindings'], target_data['results']['bindings']):
            i, mapping = 0, {}
            for result in results:
                result = sorted(result.iteritems())
                for _, value in result:
                    if value['type'] == 'bnode':
                        if value['value'] in mapping:
                            value['value'] = mapping[value['value']]
                        else:
                            value['value'] = mapping[value['value']] = i
                            i += 1

        self.assertEqual(data['head']['vars'], target_data['head']['vars'])
        self.assertEqual(data['results'], target_data['results'])

    def testValidSRJBoolean(self):
        for value in (True, False):
            data = ''.join(SRJSerializer(value))
            try:
                data = json.loads(data)
            except Exception, e:
                raise AssertionError(e)
            self.assertEqual(data, {'head': {}, 'boolean': value})

