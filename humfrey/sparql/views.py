import time
import urllib2

from lxml import etree
import rdflib
import redis

from django.conf import settings
from django_conneg.views import HTMLView, TextView

from humfrey.results.views.standard import RDFView, ResultSetView
from humfrey.results.views.feed import FeedView
from humfrey.results.views.spreadsheet import SpreadsheetView
from humfrey.results.views.geospatial import KMLView 
from humfrey.sparql.forms import SparqlQueryForm
from humfrey.utils.views import EndpointView
from humfrey.utils.namespaces import NS

class SparqlGraphView(RDFView, HTMLView, FeedView, KMLView):
    def get(self, request, context):
        x = self.render(request, context, ('sparql/graph', 'results/graph'))
        return x
    post = get

class SparqlResultSetView(ResultSetView, SpreadsheetView, HTMLView ):
    def get(self, request, context):
        x = self.render(request, context, ('sparql/resultset', 'results/resultset'))
        return x
    post = get

class SparqlBooleanView(ResultSetView, HTMLView):
    def get(self, request, context):
        return self.render(request, context, ('sparql/boolean', 'results/boolean'))
    post = get

class SparqlErrorView(HTMLView, TextView):
    _default_format = 'txt'
    _force_fallback_format = 'txt'

    def get(self, request, context):
        return self.render(request, context, 'sparql/error')
    post = get
    
    

class SparqlView(EndpointView, HTMLView):
    class SparqlViewException(Exception):
        pass
    class ConcurrentQueryException(SparqlViewException):
        pass
    class ExcessiveQueryException(SparqlViewException):
        def __init__(self, intensity):
            self.intensity = intensity

    _THROTTLE_THRESHOLD = 10
    _DENY_THRESHOLD = 20
    _INTENSITY_DECAY = 0.05
    
    _graph_view = staticmethod(SparqlGraphView.as_view())
    _resultset_view = staticmethod(SparqlResultSetView.as_view())
    _boolean_view = staticmethod(SparqlBooleanView.as_view())
    _error_view = staticmethod(SparqlErrorView.as_view())

    def perform_query(self, request, query, common_prefixes):
        if settings.REDIS_PARAMS:
            client = redis.client.Redis(**settings.REDIS_PARAMS)
            addr = request.META['REMOTE_ADDR']
            if not client.setnx('sparql:lock:%s' % addr, 1):
                raise self.ConcurrentQueryException
            try:
                intensity = float(client.get('sparql:intensity:%s' % addr) or 0)
                last = float(client.get('sparql:last:%s' % addr) or 0)
                intensity = max(0, intensity - (time.time() - last) * self._INTENSITY_DECAY)
                if intensity > self._DENY_THRESHOLD:
                    raise self.ExcessiveQueryException(intensity)
                elif intensity > self._THROTTLE_THRESHOLD:
                    time.sleep(intensity - self._THROTTLE_THRESHOLD)

                start = time.time()
                results = self.endpoint.query(query, common_prefixes=common_prefixes)
                end = time.time()

                new_intensity = intensity + end - start
                client.set('sparql:intensity:%s' % addr, new_intensity)
                client.set('sparql:last:%s' % addr, end)

                return results, new_intensity
            finally:
                client.delete('sparql:lock:%s' % addr)
        else:
            return self.endpoint.query(query, common_prefixes=common_prefixes), 0
    
    def get_format_choices(self):
        return (
            ('Graph (DESCRIBE, CONSTRUCT)',
             tuple((r.format, r.name) for r in sorted(self._graph_view._renderers, key=lambda r:r.name))),
            ('Resultset (SELECT)',
             tuple((r.format, r.name) for r in sorted(self._resultset_view._renderers, key=lambda r:r.name))),
            ('Boolean (ASK)',
             tuple((r.format, r.name) for r in sorted(self._boolean_view._renderers, key=lambda r:r.name))),
        )

    def get(self, request):
        query = request.REQUEST.get('query')
        data = dict(request.REQUEST.items())
        if not 'format' in data:
            data['format'] = 'html'
        form = SparqlQueryForm(request.REQUEST, formats=self.get_format_choices())
        context = {
            'namespaces': NS,
            'form': form,
        }

        additional_headers = context['additional_headers'] = {
            'X-Humfrey-SPARQL-Throttle-Threshold': self._THROTTLE_THRESHOLD,
            'X-Humfrey-SPARQL-Deny-Threshold': self._DENY_THRESHOLD,
            'X-Humfrey-SPARQL-Intensity-Decay': self._INTENSITY_DECAY,
        }

        if form.is_valid():
            try:
                results, intensity = self.perform_query(request, query, form.cleaned_data['common_prefixes'])
                additional_headers['X-Humfrey-SPARQL-Intensity'] = intensity
    
            except urllib2.HTTPError, e:
                context['error'] = e.read() #parse(e).find('.//pre').text
                context['status_code'] = e.code
            except self.ConcurrentQueryException, e:
                context['error'] = "You cannot perform more than one query at a time.\nPlease wait for your previous query to complete or time out first."
                context['status_code'] = 403
            except self.ExcessiveQueryException, e:
                context['error'] = "You have been performing a lot of queries recently.\nPlease wait a while and try again."
                context['status_code'] = 403
                additional_headers['X-Humfrey-SPARQL-Intensity'] = e.intensity
            except etree.XMLSyntaxError, e:
                context['error'] = "Your query could not be returned in the time allotted it.\n" \
                                 + "Please try a simpler query or using LIMIT to reduce the number of returned results."
                context['status_code'] = 403
            else:
                context['queries'] = [results.query]
                context['duration'] = results.duration

                if isinstance(results, list):
                    context['results'] = results
                    return self._resultset_view(request, context)
                elif isinstance(results, bool):
                    context['result'] = results
                    return self._boolean_view(request, context)
                elif isinstance(results, rdflib.ConjunctiveGraph):
                    context['graph'] = results
                    context['subjects'] = results.subjects()
                    return self._graph_view(request, context)

        if 'error' in context:
            return self._error_view(request, context)
        else:
            return self.render(request, context, 'sparql/index')

    post = get
