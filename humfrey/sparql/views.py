import datetime
import time
import urllib2

from lxml import etree
import pytz

from django.conf import settings
from django_conneg.views import ContentNegotiatedView, HTMLView, JSONPView, TextView, ErrorCatchingView
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from humfrey.results.views.standard import RDFView, ResultSetView
from humfrey.results.views.feed import FeedView
from humfrey.results.views.spreadsheet import SpreadsheetView
from humfrey.results.views.geospatial import KMLView
from humfrey.utils.views import RedisView
from humfrey.utils.namespaces import NS

from humfrey.sparql.endpoint import Endpoint, EndpointView, SparqlResultList, SparqlResultGraph, SparqlResultBool
from humfrey.sparql.forms import SparqlQueryForm
from humfrey.sparql.models import Store, UserPrivileges

class IndexView(HTMLView, JSONPView):
    def get(self, request):
        stores = Store.objects.all().order_by('name')
        if not request.user.is_superuser:
            stores = [s for s in stores if request.user.has_any_perms(s)]
        context = {'stores': stores}
        return self.render(request, context, 'sparql/index')

class SparqlGraphView(RDFView, HTMLView, FeedView, KMLView):
    def get(self, request, context):
        return self.render(request, context, ('sparql/graph', 'results/graph'))
    post = get

class SparqlResultSetView(ResultSetView, SpreadsheetView, HTMLView):
    def get(self, request, context):
        return self.render(request, context, ('sparql/resultset', 'results/resultset'))
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

class QueryView(EndpointView, RedisView, HTMLView, ErrorCatchingView):
    QUERY_CHANNEL = 'humfrey:sparql:query-channel'

    store = None # Use the default store
    default_timeout = None # Override this with some number of seconds
    maximum_timeout = None # Override this with some number of seconds
    allow_concurrent_queries = False

    class SparqlViewException(Exception):
        pass
    class ConcurrentQueryException(SparqlViewException):
        pass
    class ExcessiveQueryException(SparqlViewException):
        def __init__(self, intensity):
            self.intensity = intensity

    throttle_threshold = 10
    deny_threshold = 20
    intensity_decay = 0.05

    _graph_view = staticmethod(SparqlGraphView.as_view())
    _resultset_view = staticmethod(SparqlResultSetView.as_view())
    _boolean_view = staticmethod(SparqlBooleanView.as_view())
    _error_view = staticmethod(SparqlErrorView.as_view())
    
    def _get_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def get_user_privileges(self, request):
        if request.user.is_superuser:
            return {'maximum_timeout': None,
                    'throttle': False,
                    'allow_concurrent_queries': True,
                    'user_key': request.user.username}
        if not request.user.is_authenticated():
            overrides = ()
        else:
            try:
                overrides = (UserPrivileges.objects.get(user=request.user),)
            except UserPrivileges.DoesNotExist:
                overrides = UserPrivileges.objects.filter(group__user=request.user)
        privileges = {'maximum_timeout': self.maximum_timeout,
                      'throttle': True,
                      'throttle_threshold': self.throttle_threshold,
                      'deny_threshold': self.deny_threshold,
                      'intensity_decay': self.intensity_decay,
                      'allow_concurrent_queries': self.allow_concurrent_queries,
                      'user_key': request.user.username if request.user.is_authenticated() else request.META['REMOTE_ADDR']}
        for override in overrides:
            if override.disable_timeout:
                privileges['maximum_timeout'] = None
            if override.disable_throttle:
                privileges['throttle'] = False
            if override.allow_concurrent_queries:
                privileges['allow_concurrent_queries'] = True
            for name in ('maximum_timeout', 'throttle_threshold', 'deny_threshold', 'intensity_decay'):
                if privileges[name] and getattr(override, name):
                    privileges[name] = max(privileges[name], getattr(override, name))
        return privileges

    def get_timeout(self, request, privileges):
        """
        Pulls a timeout out of the request if one is given, and makes sure it
        doesn't exceed any default timeouts (either default, or user-specific).
        """

        timeout = self._get_float(request.META.get('HTTP_TIMEOUT')) \
               or self._get_float(request.REQUEST.get('timeout')) \
               or self.default_timeout
        if timeout and privileges['maximum_timeout']:
            timeout = min(timeout, privileges['maximum_timeout'])
        return timeout

    def perform_query(self, request, query, common_prefixes, privileges):
        if settings.REDIS_PARAMS:
            user_key = privileges['user_key']
            client = self.get_redis_client()
            if not privileges['allow_concurrent_queries'] and \
               not client.setnx('sparql:lock:%s' % user_key, 1):
                raise self.ConcurrentQueryException
            try:
                if privileges['throttle']:
                    intensity = float(client.get('sparql:intensity:%s' % user_key) or 0)
                    last = float(client.get('sparql:last:%s' % user_key) or 0)
                    intensity = max(0, intensity - (time.time() - last) * privileges['intensity_decay'])
                    if intensity > privileges['deny_threshold']:
                        raise self.ExcessiveQueryException(intensity)
                    elif intensity > privileges['throttle_threshold']:
                        time.sleep(intensity - privileges['throttle_threshold'])

                    start = time.time()

                results = self.endpoint.query(query,
                                              common_prefixes=common_prefixes,
                                              timeout=self.get_timeout(request, privileges))

                if privileges['throttle']:
                    end = time.time()

                    new_intensity = intensity + end - start
                    client.set('sparql:intensity:%s' % user_key, new_intensity)
                    client.set('sparql:last:%s' % user_key, end)
                else:
                    new_intensity = None

                client.publish(self.QUERY_CHANNEL,
                               self.pack({'query': query,
                                          'common_prefixes': common_prefixes,
                                          'accept': request.META.get('HTTP_ACCEPT'),
                                          'user_agent': request.META.get('HTTP_USER_AGENT'),
                                          'referer': request.META.get('HTTP_REFERER'),
                                          'origin': request.META.get('HTTP_ORIGIN'),
                                          'date': pytz.utc.localize(datetime.datetime.utcnow()),
                                          'remote_addr': request.META.get('REMOTE_ADDR'),
                                          'format_param': request.REQUEST.get('format'),
                                          'formats': [r.format for r in self.get_renderers(request)],
                                          'intensity': new_intensity,
                                          'duration': results.duration,
                                          'user': request.user if request.user.is_authenticated() else None,
                                          'successful': True}))

                return results, new_intensity
            finally:
                if not privileges['allow_concurrent_queries']:
                    client.delete('sparql:lock:%s' % user_key)
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

    def get(self, request, store=None):
        store = store or self.store
        if store is not None:
            store = get_object_or_404(Store, slug=store)
            if not store.can_query(request.user):
                raise PermissionDenied
            self.endpoint = Endpoint(store.query_endpoint)

        privileges = self.get_user_privileges(request)

        query = request.REQUEST.get('query')
        form = SparqlQueryForm(request.REQUEST if query else None,
                               formats=self.get_format_choices())

        context = {
            'namespaces': sorted(NS.items()),
            'form': form,
            'store': store,
        }

        if privileges['throttle']:
            additional_headers = context['additional_headers'] = {
                'X-Humfrey-SPARQL-Throttle-Threshold': privileges['throttle_threshold'],
                'X-Humfrey-SPARQL-Deny-Threshold': privileges['deny_threshold'],
                'X-Humfrey-SPARQL-Intensity-Decay': privileges['intensity_decay'],
            }

        if form.is_valid():
            try:
                results, intensity = self.perform_query(request, query, form.cleaned_data['common_prefixes'], privileges)
                if intensity is not None:
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

                if isinstance(results, SparqlResultList):
                    context['results'] = results
                    return self._resultset_view(request, context)
                elif isinstance(results, SparqlResultBool):
                    context['result'] = results
                    return self._boolean_view(request, context)
                elif isinstance(results, SparqlResultGraph):
                    context['graph'] = results
                    context['subjects'] = results.subjects()
                    return self._graph_view(request, context)
                else:
                    raise AssertionError("Unexpected return type: %r" % type(results))

        if 'error' in context:
            return self._error_view(request, context)
        else:
            return self.render(request, context, 'sparql/query')

    post = get
