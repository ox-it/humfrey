import base64
import hashlib
import logging
import pickle

import rdflib

from django.core.cache import cache
from django.conf import settings

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
        if response.renderer:
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
