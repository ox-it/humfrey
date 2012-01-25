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
