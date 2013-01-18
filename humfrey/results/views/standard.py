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
              name=streaming_format['name'])
    def render(self, request, context, template_name):
        results = context.get('results')
        try:
            data = iter(serializer_class(results))
            return HttpResponse(data, mimetype=mimetype)
        except TypeError:
            raise
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


class ResultSetiew(ContentNegotiatedView):

    def render_resultset(self, request, context, spool_boolean, spool_resultset, mimetype):
        try:
            sparql_results_type = context['results'].get_sparql_results_type()
        except:
            return NotImplemented
        if sparql_results_type == 'boolean':
            spool = spool_boolean(context['results'])
        elif sparql_results_type == 'resultset':
            spool = spool_resultset(context['results'])
        else:
            raise AssertionError("Unexpected SPARQL results type: {0}".format(sparql_results_type))
        return HttpResponse(spool, mimetype=mimetype)

    @renderer(format='srx', mimetypes=('application/sparql-results+xml',), name='SPARQL Results XML')
    def render_srx(self, request, context, template_name):
        try:
            return HttpResponse(iter(srx.SRXSerializer(context.get('results'))),
                                mimetype='application/sparql-results+xml')
        except TypeError:
            return NotImplemented

    @renderer(format='srj', mimetypes=('application/sparql-results+json',), name='SPARQL Results JSON')
    def render_srj(self, request, context, template_name):
        try:
            results = iter(srj.SRJSerializer(context.get('results')))
        except TypeError:
            return NotImplemented
        callback = request.GET.get('callback')
        mimetype = 'application/javascript' if callback else 'application/sparql-results+json'
        if callback:
            results = itertools.chain([callback, '('], results, [');\n'])
        return HttpResponse(results, mimetype=mimetype)

    @renderer(format='csv', mimetypes=('text/csv',), name='CSV')
    def render_csv(self, request, context, template_name):
        try:
            return HttpResponse(iter(csv.CSVSerializer(context.get('results'))),
                                mimetype='text/csv')
        except TypeError:
            return NotImplemented
