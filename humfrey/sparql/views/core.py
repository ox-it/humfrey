import base64
import functools
import hashlib
import http.client
import math
import pickle
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from lxml import etree
import rdflib
import redis

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.views.generic import View

from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView, HTMLView

from humfrey.linkeddata.resource import Resource
from humfrey.linkeddata.views import MappingView
from humfrey.misc.views import PassThroughView
from humfrey.results.views.standard import RDFView, ResultSetView
from humfrey.utils.views import RedisView
from humfrey.utils.namespaces import NS

from humfrey.sparql.endpoint import Endpoint, QueryError
from humfrey.sparql.forms import SparqlQueryForm
from humfrey.sparql.models import Store

DEFAULT_STORE_NAME = getattr(settings, 'DEFAULT_STORE_NAME', 'public')

class SparqlGraphView(RDFView, HTMLView):
    def get(self, request, context):
        return self.render(request, context, ('sparql/query', 'results/graph'))
    post = get

class SparqlResultsView(ResultSetView, HTMLView):
    def get(self, request, context):
        return self.render(request, context, ('sparql/query', 'results/resultset'))
    post = get

class StoreView(View):
    store_name = DEFAULT_STORE_NAME # Use the default store

    @property
    def store(self):
        if not hasattr(self, '_store'):
            self._store = get_object_or_404(Store, slug=self.store_name)
        return self._store

    @property
    def endpoint(self):
        if not hasattr(self, '_endpoint'):
            if isinstance(self, ContentNegotiatedView):
                self.set_renderers(early=True)
                preferred_media_types = [m.value for r in self.request.renderers for m in r.mimetypes]
            else:
                preferred_media_types = ()
            self._endpoint = Endpoint(self.store.query_endpoint,
                                      preferred_media_types=preferred_media_types)
        return self._endpoint

    def dispatch(self, request, *args, **kwargs):
        response = super(StoreView, self).dispatch(request, *args, **kwargs)
        response['X-Humfrey-Store-Name'] = self.store.slug
        return response

    def get_types(self, uri):
        if ' ' in uri:
            return set()
        parsed = urllib.parse.urlparse(uri)
        if parsed.scheme == 'mailto':
            if parsed.netloc or not parsed.path:
                return set()
        else:
            if not (parsed.scheme and parsed.netloc):
                return set()
        key_name = 'types:%s' % hashlib.sha256(uri.encode('utf8')).hexdigest()
        types = cache.get(key_name)
        if False and types:
            types = pickle.loads(base64.b64decode(types))
        else:
            results = self.endpoint.query('SELECT ?type WHERE { %s a ?type }' % uri.n3(),
                                          preferred_media_types=('application/sparql-results+xml',))
            types = set(rdflib.URIRef(r.type) for r in results)
            cache.set(key_name, base64.b64encode(pickle.dumps(types)), 1800)
        return types

    def update_context_for_deferral(self):
        """
        Adds elements to the context for undeferring and accessing elements of
        the query response from a template.
        """
        def deferred(name):
            def f():
                self.undefer()
                return self.context['_'+name]
            return f
        for name in ('subjects', 'fields', 'bindings', 'graph'):
            self.context[name] = deferred(name)

    def undefer(self):
        """
        Undefers parsing of a query response in the context.

        The parsed query results are put back in the context in appropriately
        named variables. Can be called more than once, with successive calls
        as no-ops. Access the results using the names without underscores (as
        placed in the context by calling update_context_for_deferral()), to
        only undefer if necessary.
        """
        context = self.context
        results = context.pop('results', None)
        if not results:
            return
        sparql_results_type = results.get_sparql_results_type()
        context['_sparql_results_type'] = sparql_results_type
        context['_' + sparql_results_type] = results.get()
        if sparql_results_type == 'resultset':
            context['_fields'] = results.get_fields()
            context['_bindings'] = context['resultset']
        elif sparql_results_type == 'graph':
            graph = context['_graph']
            self.resource = functools.partial(Resource, graph=graph, endpoint=self.endpoint)
            subjects = list(map(self.resource, self.get_subjects(graph)))
            self.sort_subjects(subjects)
            context['_subjects'] = subjects

    def get_subjects(self, graph):
        return graph.objects(rdflib.URIRef(self.request.build_absolute_uri()),
                             NS.foaf.topic)

    def sort_subjects(self, subjects):
        def k(s):
            return str(s.label)
        subjects.sort(key=k)

class QueryView(StoreView, MappingView, RedisView, HTMLView, RDFView, ResultSetView):
    QUERY_CHANNEL = 'humfrey:sparql:query-channel'

    _force_fallback_format = 'html'

    template_name = 'sparql/query'

    default_timeout = None # Override this with some number of seconds
    maximum_timeout = None # Override this with some number of seconds

    _graph_view = staticmethod(SparqlGraphView.as_view())
    _sparql_results_view = staticmethod(SparqlResultsView.as_view())

    _passthrough_view = staticmethod(PassThroughView.as_view())

    def _get_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_timeout(self, request):
        """
        Pulls a timeout out of the request if one is given, and makes sure it
        doesn't exceed any default timeouts (either default, or user-specific).
        """

        timeout = self._get_float(request.META.get('HTTP_TIMEOUT')) \
               or self._get_float(request.POST.get('timeout')) \
               or self._get_float(request.GET.get('timeout')) \
               or self.default_timeout
        if timeout and self.maximum_timeout:
            timeout = min(timeout, self.maximum_timeout)
        return timeout

    def perform_query(self, request, query, common_prefixes):
        timeout = self._get_timeout(request)
        return self.endpoint.query(query,
                                   common_prefixes=common_prefixes,
                                   timeout=timeout,
                                   defer=True)

    def get_format_choices(self):
        return (
            ('', 'Automatic'),
            ('Graph (DESCRIBE, CONSTRUCT)',
             tuple((r.format, r.name) for r in sorted(self._graph_view.conneg.renderers, key=lambda r:r.name))),
            ('SPARQL Results (SELECT, ASK)',
             tuple((r.format, r.name) for r in sorted(self._sparql_results_view.conneg.renderers, key=lambda r:r.name))),
        )

    def get(self, request):
        request_data = request.POST if request.method == 'POST' else request.GET
        query = request_data.get('query')
        form = SparqlQueryForm(request_data if query else None,
                               formats=self.get_format_choices())

        context = self.context
        context.update({
            'namespaces': sorted(NS.items()),
            'form': form,
            'store': self.store
        })

        if form.is_valid():
            try:
                results = self.perform_query(request, query, form.cleaned_data['common_prefixes'])
            except QueryError as e:
                context['error'] = e.message
                context['status_code'] = e.status_code
            else:
                context['additional_headers']['X-Humfrey-SPARQL-Duration'] = results.duration

                context['queries'] = [results.query]
                context['duration'] = results.duration
                context['results'] = results

                if results.format_type == 'sparql-results':
                    return self._sparql_results_view(request, context)
                elif results.format_type == 'graph':
                    return self._graph_view(request, context)
                raise AssertionError("Unexpected format type: {0}".format(results.format_type))

        return self.render()

    post = get

class ProtectedQueryView(QueryView):
    """
    Like a QueryView, but with protection against abuse through rate-limiting.

    The durations of queries contribute to an intensity, which invokes
    rate-limiting when it gets too high. This intensity decays over time.

    When the intensity reaches the throttle threshold, the view delays the
    query for a while to slow down the query rate for a user. When it reaches
    the deny threshold we return 503 Service Unavailable and tell the user
    when they can expect a query next to be accepted using the Retry-After
    header.

    Currently-running queries for a user are stored in redis. Their cumulative
    running time is added to the intensity score. This means that the more
    concurrent queries a user runs, the higher the rate of increase.

    Each running query maintains a heartbeat, lest they die in unexpected
    ways, such as an unexpected server restart. Any queries that have expired
    are removed and ignored, and so don't contribute to the intensity.

    The default limits are kept quite high, and should ordinarily not affect
    casual users. If you have concerns, you can fiddle with the numbers below.
    """

    error_template_name = 'sparql/error'

    # Information about individual queries ({0} will be a UUID)
    user_queries_key = 'humfrey:sparql:queries:{0}'
    # These too record the intensity and the last time it was updated for each
    # user_key. One needs to subtract the difference between now and when it
    # was updated, multiplied by the decay factor to find the actual intensity.
    intensity_updated_key = 'humfrey:sparql:intensity-updated:{0}'
    intensity_value_key = 'humfrey:sparql:intensity-value:{0}'
    # For each user_key, a set of UUIDs of their current queries.
    query_key = 'humfrey:sparql:query:{0}'

    # For queries that haven't started, or which haven't been going very long,
    # this is their (minimum) contribution towards the intensity
    minimum_query_intensity = 2
    # Intensity decays at this rate of seconds per second.
    intensity_decay = 0.05
    # Once the intensity reaches this number of seconds, any further queries
    # will be delayed by the difference
    throttle_threshold = 15
    # Once the intensity reaches this number of seconds, queries will be
    # refused outright
    deny_threshold = 30
    # Number of seconds between heartbeats to mark a query as still alive
    heartbeat_frequency = 4

    class SparqlViewException(Exception):
        pass
    class ExcessiveQueryException(SparqlViewException):
        message = "You have been performing a lot of queries recently.\nPlease wait a while and try again."
        def __init__(self, intensity, threshold):
            self.intensity, self.threshold = intensity, threshold

    def get_user_key(self, request):
        if request.user.is_authenticated:
            return request.user.id
        else:
            return request.META['REMOTE_ADDR']

    def get_current_queries(self, client, user_key):
        uuids = client.smembers(self.user_queries_key.format(user_key))
        if not uuids:
            return
        queries = list(map(self.unpack, client.mget([self.query_key.format(u) for u in uuids])))
        for query in queries:
            if not query:
                continue
            if 'started' in query:
                query['intensity'] = max(self.minimum_query_intensity,
                                         time.time() - query['started'])
            else:
                query['intensity'] = self.minimum_query_intensity
            if time.time() > query['heartbeat']:
                user_queries_key = self.user_queries_key.format(user_key)
                client.srem(user_queries_key, query['id'])
                client.delete(self.query_key.format(query['id']))
                continue
            yield query

    def get_intensity(self, client, user_key, queries):
        updated_key = self.intensity_updated_key.format(user_key)
        value_key = self.intensity_value_key.format(user_key)

        updated = float(client.get(updated_key) or time.time())
        value = float(client.get(value_key) or 0)

        value += sum(query['intensity'] for query in queries)
        value -= (time.time() - updated) * self.intensity_decay
        return max(0, value)

    def perform_query(self, request, query, common_prefixes):
        client = self.get_redis_client()
        user_key = self.get_user_key(request)
        queries = self.get_current_queries(client, user_key)
        intensity = self.get_intensity(client, user_key, queries)

        # These might be useful things for a client to know
        self.context['additional_headers'].update({'X-Humfrey-SPARQL-Throttle-Threshold': self.throttle_threshold,
                                                   'X-Humfrey-SPARQL-Deny-Threshold': self.deny_threshold,
                                                   'X-Humfrey-SPARQL-Intensity-Decay': self.intensity_decay})

        if intensity > self.deny_threshold:
            # Refuse the query outright
            raise self.ExcessiveQueryException(intensity, self.deny_threshold)

        query_id = uuid.uuid4().hex
        query_key = self.query_key.format(query_id)
        user_queries_key = self.user_queries_key.format(user_key)

        # Store details of the query in redis. Don't store 'started' until
        # we've done any throttling
        data = {'query': query,
                'id': query_id,
                'common_prefixes': common_prefixes,
                'user_key': user_key,
                'requested': time.time(),
                'heartbeat': time.time() + self.heartbeat_frequency * 2}
        client.set(query_key, self.pack(data))
        client.sadd(user_queries_key, query_id)

        # This thread will update the heartbeat on the query every few seconds.
        # The query_done event is used to tell it to stop beating and exit.
        query_done = threading.Event()
        heartbeat_thread = threading.Thread(target=self._heartbeat, args=(client, query_key, query_done, self.heartbeat_frequency))

        try:
            heartbeat_thread.start()

            # Throttle if necessary
            if intensity > self.throttle_threshold:
                throttle_by = intensity - self.throttle_threshold
                self.context['additional_headers']['X-Humfrey-SPARQL-Throttled-By'] = throttle_by
                time.sleep(throttle_by)

            # Record the started time in redis
            started = time.time()
            self._update_redis_dict(client, query_key, {'started': started})

            return super(ProtectedQueryView, self).perform_query(request, query, common_prefixes)
        finally:
            # Tell the heatbeat thread that its work is done.
            query_done.set()

            # Update the query intensity.
            new_intensity = self._update_intensity(client, user_key, time.time() - started)
            self.context['additional_headers'].update({'X-Humfrey-SPARQL-Intensity': new_intensity})

            # Remove the record of the query from redis, so that it no longer
            # counts towards the intensity.
            client.srem(user_queries_key, query_id)
            client.delete(query_key)

    def _heartbeat(self, client, query_key, query_done, heartbeat_frequency):
        while not query_done.wait(self.heartbeat_frequency):
            # In Py2.6, Event.wait() always returns None, so we need this check
            if query_done.is_set():
                break
            new_data = {'heartbeat': time.time() + heartbeat_frequency * 2}
            self._update_redis_dict(client, query_key, new_data)

    def _update_redis_dict(self, client, key, new_data):
        """
        Updates a packed dictionary in redis in a thread-safe manner.
        """
        # This is optimistic concurrency control (optimistic locking)
        # We watch the key we're going to change, attempt to make the changes,
        # and abort and try again if the key has been changed in the meantime.
        # In the vast majority of cases this will succeed first time, but
        # without doing this we might end up in a permanently inconsistent
        # state.
        while True:
            with client.pipeline() as pipeline:
                try:
                    pipeline.watch(key)
                    data = pipeline.get(key)
                    if not data:
                        break
                    data = self.unpack(data)
                    data.update(new_data)
                    pipeline.multi()
                    pipeline.set(key, self.pack(data))
                    pipeline.execute()
                except redis.WatchError:
                    continue
                else:
                    break

    def _update_intensity(self, client, user_key, duration):
        """
        Adds duration to the intensity for a given user_key.
        """
        # More optimistic locking
        while True:
            intensity_updated_key = self.intensity_updated_key.format(user_key)
            intensity_value_key = self.intensity_value_key.format(user_key)
            try:
                with client.pipeline() as pipeline:
                    pipeline.watch(intensity_updated_key, intensity_value_key)
                    updated = float(pipeline.get(intensity_updated_key) or time.time())
                    value = float(pipeline.get(intensity_value_key) or 0)
                    value -= (time.time() - updated) * self.intensity_decay
                    value = max(value, 0)
                    value += min(0.2, duration)
                    pipeline.multi()
                    pipeline.set(intensity_updated_key, time.time())
                    pipeline.set(intensity_value_key, value)
                    pipeline.execute()
                    return value
            except redis.WatchError:
                continue
            else:
                break

    def dispatch(self, request):
        try:
            return super(ProtectedQueryView, self).dispatch(request)
        except urllib.error.HTTPError as e:
            self.context.update({'error': {'message': e.read(),
                                           'status_code': e.code}})
            return self.error_view(request, self.context, self.error_template_name)
        except self.SparqlViewException as e:
            self.context.update({'error': {'message': e.message,
                                           'status_code': http.client.SERVICE_UNAVAILABLE}})
            if hasattr(e, 'intensity'):
                retry_after = int(math.ceil((e.intensity - self.deny_threshold) / self.intensity_decay) + 1)
                self.context['additional_headers'].update({'X-Humfrey-SPARQL-Intensity': e.intensity,
                                                           'Retry-After': retry_after})
            return self.error_view(request, self.context, self.error_template_name)
        except etree.XMLSyntaxError as e:
            self.context.update({'error': {'message': "Your query could not be returned in the time allotted it.\n" \
                                                    + "Please try a simpler query or using LIMIT to reduce the number of returned results.",
                                           'status_code': http.client.FORBIDDEN}})
            return self.error_view(request, self.context, self.error_template_name)

class GraphStoreView(StoreView, PassThroughView):
    def get_target_url(self, request, path=None, store=None):
        if not path and 'graph' in request.GET:
            graph_url = request.GET['graph']
        else:
            graph_url = request.build_absolute_uri()
        return '%s?%s' % (self.store.graph_store_endpoint,
                          urllib.parse.urlencode({'graph': graph_url.decode('utf-8')}))
    def get_method(self, request, path=None, store=None):
        if request.method in ('HEAD', 'GET'):
            permission_check = self.store.can_query
        else:
            permission_check = self.store.can_update
        if not permission_check(request.user):
            raise PermissionDenied
        return request.method
