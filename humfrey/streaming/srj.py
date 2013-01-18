try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import rdflib

from humfrey.sparql.results import Result
from humfrey.utils import json

from .base import StreamingParser, StreamingSerializer

_type_mapping = {'uri': lambda v: rdflib.URIRef(v['value']),
                 'bnode': lambda v: rdflib.BNode(v['value']),
                 'literal': lambda v: rdflib.Literal(v['value'], datatype=v['datatype']),
                 'typed-literal': lambda v: rdflib.Literal(v['value'], language=v.get('xml:lang'))}

class SRJParser(StreamingParser):
    media_type = 'application/sparql-results+json'

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
            for name, value in binding.iteritems():
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

    def _iter(self, sparql_results_type, fields, bindings, boolean, triples):
        if sparql_results_type not in ('resultset', 'boolean'):
            raise TypeError("Unexpected results type: {0}".format(sparql_results_type))

        # We'll spool to a buffer, and only yield when it gets a bit big.
        buffer = StringIO()

        # Do these attribute lookups only once.
        json_dumps, json_dump, buffer_write = json.dumps, json.dump, buffer.write

        buffer_write('{\n')
        if sparql_results_type == 'boolean':
            buffer_write('  "head": {},\n')
            buffer_write('  "boolean": %s\n' % ('true' if boolean else 'false'))
        elif sparql_results_type == 'resultset':
            buffer_write('  "head": {\n')
            buffer_write('    "vars": [ %s ]\n' % ', '.join(json_dumps(field) for field in fields))
            buffer_write('  },\n')
            buffer_write('  "results": {\n')
            buffer_write('    "bindings": [\n')
            for i, binding in enumerate(bindings):
                buffer_write('      {' if i == 0 else ',\n      {')
                j = 0
                for field in fields:
                    value = binding.get(field)
                    if value is None:
                        continue
                    buffer_write(',\n        ' if j > 0 else '\n        ')
                    json_dump(field, buffer)
                    if isinstance(value, rdflib.URIRef):
                        buffer_write(': { "type": "uri"')
                    elif isinstance(value, rdflib.BNode):
                        buffer_write(': { "type": "bnode"')
                    elif value.datatype is not None:
                        buffer_write(': { "type": "typed-literal", "datatype": ')
                        json_dump(value.datatype, buffer)
                    elif value.language is not None:
                        buffer_write(': { "type": "literal", "xml:lang": ')
                        json_dump(value.language, buffer)
                    else:
                        buffer_write(': { "type": "literal"')
                    buffer_write(', "value": ')
                    json_dump(value, buffer)
                    buffer_write(' }')

                    j += 1

                buffer_write('\n      }')


            if buffer.tell() > 65000: # Almost 64k
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()

        buffer_write('\n    ]\n')
        buffer_write('  }\n')
        buffer_write('}')
        yield buffer.getvalue()
        buffer.close()
