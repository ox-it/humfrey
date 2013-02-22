from __future__ import absolute_import

import types

from django.http import HttpResponse

from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView

from humfrey import streaming
from humfrey.streaming.base import StreamingParser

def get_renderer_test(serializer_class):
    def test(self, request, context, template_name):
        if isinstance(context.get('results'), StreamingParser):
            return serializer_class.format_type == context['results'].format_type
        if serializer_class.format_type == 'sparql-results':
            return 'bindings' in context or 'boolean' in context
        elif serializer_class.format_type == 'graph':
            return 'graph' in context
        else:
            return False
    return test

def get_renderer(streaming_format):
    serializer_class = streaming_format['serializer']
    mimetype = streaming_format['media_type']

    @renderer(format=streaming_format['format'],
              mimetypes=(mimetype,),
              name=streaming_format['name'],
              priority=streaming_format.get('priority', 1),
              test=get_renderer_test(serializer_class))
    def render(self, request, context, template_name):
        results = context.get('results') \
               or context.get('graph') \
               or context.get('bindings') \
               or context.get('boolean')
        if isinstance(results, types.FunctionType):
            results = results()
        try:
            data = iter(serializer_class(results))
            return HttpResponse(data, mimetype=mimetype)
        except TypeError:
            return NotImplemented
    render.__name__ = 'render_%s' % streaming_format['format']
    return render

renderers = {}
for f in streaming.formats:
    if 'graph' not in f['supported_results_types'] or not f.get('serializer'):
        continue
    render = get_renderer(f)
    renderers[render.__name__] = render
RDFView = type('RDFView', (ContentNegotiatedView,), renderers)

renderers = {}
for f in streaming.formats:
    if 'resultset' not in f['supported_results_types'] or not f.get('serializer'):
        continue
    render = get_renderer(f)
    renderers[render.__name__] = render
ResultSetView = type('ResultSetView', (ContentNegotiatedView,), renderers)
