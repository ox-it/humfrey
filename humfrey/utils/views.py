import base64
import hashlib
import logging
import pickle
import urllib
import urlparse

import rdflib
import redis

from django.core.cache import cache
from django.conf import settings
from django.views.generic import View
from django.http import HttpResponsePermanentRedirect
from django_conneg.http import HttpResponseSeeOther

logger = logging.getLogger('core.requests')

from django_conneg.views import ContentNegotiatedView
from humfrey.utils import sparql

class CachedView(ContentNegotiatedView):
    def dispatch(self, request, *args, **kwargs):
        renderers = self.get_renderers(request)
        uri = request.build_absolute_uri()
        for renderer in renderers:
            key = hashlib.sha1('pickled-response:%s:%s' % (renderer.format, uri)).hexdigest()
            pickled_response = cache.get(key)
            if pickled_response is not None:
                try:
                    return pickle.loads(base64.b64decode(pickled_response))
                except Exception:
                    pass

        response = super(CachedView, self).dispatch(request, *args, **kwargs)
        if getattr(response, 'renderer', None):
            key = hashlib.sha1('pickled-response:%s:%s' % (response.renderer.format, uri)).hexdigest()
            try:
                pickled_response = base64.b64encode(pickle.dumps(response))
            except Exception:
                pass
            else:
                cache.set(key, pickled_response, settings.CACHE_TIMES['page'])
        return response

class EndpointView(ContentNegotiatedView):
    endpoint = sparql.Endpoint(settings.ENDPOINT_QUERY)

    def get_types(self, uri):
        if ' ' in uri:
            return set()
        key_name = 'types:%s' % hashlib.sha1(uri.encode('utf8')).hexdigest()
        types = cache.get(key_name)
        if False and types:
            types = pickle.loads(base64.b64decode(types))
        else:
            types = set(rdflib.URIRef(r.type) for r in self.endpoint.query('SELECT ?type WHERE { %s a ?type }' % uri.n3()))
            cache.set(key_name, base64.b64encode(pickle.dumps(types)), 1800)
        return types

class RedisView(View):
    @classmethod
    def pack(self, value):
        return base64.b64encode(pickle.dumps(value))
    @classmethod
    def unpack(self, value):
        return pickle.loads(base64.b64decode(value))
    @classmethod
    def get_redis_client(self):
        return redis.client.Redis(**settings.REDIS_PARAMS)

class SecureView(View):
    force_https = getattr(settings, 'FORCE_ADMIN_HTTPS', True)

    def dispatch(self, request, *args, **kwargs):
        if self.force_https and not (settings.DEBUG or request.is_secure()):
            url = urlparse.urlparse(request.build_absolute_uri())
            url = urlparse.urlunparse(('https',) + url[1:])
            return HttpResponsePermanentRedirect(url)
        return super(SecureView, self).dispatch(request, *args, **kwargs)

class AuthenticatedView(SecureView):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            url = '%s?%s' % (settings.LOGIN_URL,
                             urllib.urlencode({'next': request.build_absolute_uri()}))
            return HttpResponseSeeOther(url)
        return super(AuthenticatedView, self).dispatch(request, *args, **kwargs)
