import io

import rdflib

from humfrey.sparql.results import Result
from humfrey.utils import json

from .base import StreamingParser, StreamingSerializer

_type_mapping = {'uri': lambda v: rdflib.URIRef(v['value']),
                 'bnode': lambda v: rdflib.BNode(v['value']),
                 'literal': lambda v: rdflib.Literal(v['value'], datatype=v.get('xml:lang')),
                 'typed-literal': lambda v: rdflib.Literal(v['value'], language=v['datatype'])}

class SRJParser(StreamingParser):
    media_type = 'application/sparql-results+json'
    format_type = 'sparql-results'

    def get_sparql_results_type(self):
        if hasattr(self, '_sparql_results_type'):
            return self._sparql_results_type
        self.mode = 'parse'
        self._data = json.load(self._stream, self._encoding)
        if 'boolean' in self._data:
            self._sparql_results_type = 'boolean'
        else:
            self._sparql_results_type = 'resultset'
        return self._sparql_results_type

    def get_fields(self):
        if self.get_sparql_results_type() == 'resultset':
            return self._data['head']['vars']
        else:
            raise TypeError("This isn't a resultset.")

    def get_bindings(self):
        fields = self.get_fields()

        for binding in self._data['results']['bindings']:
            for name, value in binding.items():
                binding[name] = _type_mapping[value['type']](value)
            yield Result(fields, binding)

    def get_boolean(self):
        if self.get_sparql_results_type() == 'boolean':
            return self._data['boolean']
        else:
            raise TypeError("This isn't a boolean result.")

    def get_triples(self):
        raise TypeError("This isn't a graph result.")

class SRJSerializer(StreamingSerializer):
    media_type = 'application/sparql-results+json'
    supported_results_types = ('resultset', 'boolean')
    format_type = 'sparql-results'

    def _iter(self, sparql_results_type, fields, bindings, boolean, triples):
        if sparql_results_type not in ('resultset', 'boolean'):
            raise TypeError("Unexpected results type: {0}".format(sparql_results_type))

        # We'll spool to a buffer, and only yield when it gets a bit big.
        buffer = io.BytesIO()

        # Do these attribute lookups only once.
        json_dumps, buffer_write = json.dumps, buffer.write

        buffer_write(b'{\n')
        if sparql_results_type == 'boolean':
            buffer_write(b'  "head": {},\n')
            buffer_write('  "boolean": {}'.format('true' if boolean else 'false').encode())
        elif sparql_results_type == 'resultset':
            buffer_write(b'  "head": {\n')
            buffer_write('    "vars": [ {} ]\n'.format(', '.join(json_dumps(field) for field in fields)).encode())
            buffer_write(b'  },\n')
            buffer_write(b'  "results": {\n')
            buffer_write(b'    "bindings": [\n')
            for i, binding in enumerate(bindings):
                buffer_write(b'      {' if i == 0 else b',\n      {')
                j = 0
                for field in fields:
                    value = binding.get(field)
                    if value is None:
                        continue
                    buffer_write(b',\n        ' if j > 0 else b'\n        ')
                    buffer_write(json.dumps(field).encode())
                    if isinstance(value, rdflib.URIRef):
                        buffer_write(b': { "type": "uri"')
                    elif isinstance(value, rdflib.BNode):
                        buffer_write(b': { "type": "bnode"')
                    elif value.datatype is not None:
                        buffer_write(b': { "type": "typed-literal", "datatype": ')
                        buffer_write(json.dumps(value.datatype).encode())
                    elif value.language is not None:
                        buffer_write(b': { "type": "literal", "xml:lang": ')
                        buffer_write(json.dumps(value.language).encode())
                    else:
                        buffer_write(b': { "type": "literal"')
                    buffer_write(b', "value": ')
                    buffer_write(json.dumps(value).encode())
                    buffer_write(b' }')

                    j += 1

                buffer_write(b'\n      }')
            buffer_write(b'\n    ]')
            buffer_write(b'\n  }')


            if buffer.tell() > 65000: # Almost 64k
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()

        buffer_write(b'\n}')
        yield buffer.getvalue()
        buffer.close()
