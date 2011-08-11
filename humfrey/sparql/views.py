import time
import urllib2

from lxml import etree
import rdflib
import redis

from django.conf import settings
from django_conneg.views import HTMLView

from humfrey.linkeddata.views import RDFView, ResultSetView
from humfrey.sparql.forms import SparqlQueryForm
from humfrey.utils.namespaces import NS

class SparqlView(RDFView, ResultSetView, HTMLView):
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

    def get(self, request):
        query = request.REQUEST.get('query')
        data = dict(request.REQUEST.items())
        if not 'format' in data:
            data['format'] = 'html'
        form = SparqlQueryForm(data if query else None, formats=self._renderers_by_format)
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
                if isinstance(results, list):
                    context['results'] = results
                elif isinstance(results, bool):
                    context['result'] = results
                elif isinstance(results, rdflib.ConjunctiveGraph):
                    context['graph'] = results
                    context['subjects'] = results.subjects()

                context['queries'] = [results.query]
                context['duration'] = results.duration

        return self.render(request, context, 'sparql')
    post = get