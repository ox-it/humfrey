import pkgutil
import unittest

from humfrey.utils import json

from .. import SRJSerializer
from .data import TEST_RESULTSET

class SRJSerializerTestCase(unittest.TestCase):

    def testValidSRJResultSet(self):
        data = b''.join(SRJSerializer(TEST_RESULTSET))

        target_data = json.loads(pkgutil.get_data('humfrey.tests', 'data/linkeddata/srj_resultset.json'))

        try:
            data = json.loads(data.decode())
        except Exception as e:
            raise AssertionError(e)

        # Rename bnodes in the order they appear. Otherwise we're comparing
        # arbitrary strings that actually mean the same thing.
        for results in (data['results']['bindings'], target_data['results']['bindings']):
            i, mapping = 0, {}
            for result in results:
                result = sorted(result.items())
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
            data = b''.join(SRJSerializer(value))
            try:
                data = json.loads(data.decode())
            except Exception as e:
                raise AssertionError(e)
            self.assertEqual(data, {'head': {}, 'boolean': value})

