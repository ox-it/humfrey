from __future__ import absolute_import

import itertools
import imp
import rdflib.plugin
try: # This moved during the transition from rdflib 2.4 to rdflib 3.0.
    from rdflib.serializer import Serializer # 3.0
except ImportError:
    from rdflib.syntax.serializers import Serializer # 2.4

from django.http import HttpResponse

from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView

from humfrey import streaming
from humfrey.utils.statsd import statsd

def get_renderer(streaming_format):
    serializer_class = streaming_format['serializer']
    mimetype = streaming_format['media_type']

    @renderer(format=streaming_format['format'],
              mimetypes=(mimetype,),
              name=streaming_format['name'],
              priority=streaming_format.get('priority', 1))
    def render(self, request, context, template_name):
        results = context.get('results')
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
