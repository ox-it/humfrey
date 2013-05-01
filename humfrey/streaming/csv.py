
from .base import StreamingSerializer

def _quote(value):
    if value is None:
        return ''
    value = value.replace('"', '""').encode('utf-8')
    if any(bad_char in value for bad_char in '\n" ,'):
        value = '"%s"' % value
    return value

class CSVSerializer(StreamingSerializer):
    media_type = 'text/csv'
    format_type = 'sparql-results'
    supported_results_types = ('resultset', 'boolean')

    def _iter(self, sparql_results_type, fields, bindings, boolean, triples):
        if sparql_results_type == 'resultset':
            yield ','.join(_quote(field) for field in fields)
            yield '\n'
            for binding in bindings:
                yield ','.join(_quote(value) for value in binding)
                yield '\n'
        elif sparql_results_type == 'boolean':
            yield 'true\n' if boolean else 'false\n'
        else:
            raise TypeError("Unexpected result type: {0}".format(sparql_results_type))
