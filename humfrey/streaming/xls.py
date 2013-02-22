from django.template import Context, loader
from .base import StreamingSerializer

def _quote(value):
    if value is None:
        return ''
    value = value.replace('"', '""')
    if any(bad_char in value for bad_char in '\n" ,'):
        value = '"%s"' % value
    return value

class XLSSerializer(StreamingSerializer):
    media_type = 'application/vnd.ms-excel'
    format_type = 'sparql-results'
    supported_results_types = ('resultset', 'boolean')

    def _iter(self, sparql_results_type, fields, bindings, boolean, triples):
        template = loader.get_template('streaming/resultset.xls')
        context = Context({'fields': fields,
                           'bindings': bindings,
                           'boolean': boolean})
        return iter([template.render(context)])