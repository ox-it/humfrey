try:
    import simplejson as json
except ImportError:
    import json
import http.client
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from humfrey.sparql.models import Store
from humfrey.elasticsearch.models import Index
from humfrey.update.tasks.retrieve import USER_AGENTS

logger = logging.getLogger(__name__)

class BadQueryException(Exception):
    def __init__(self, query, error):
        self.query, self.error = query, error

    def __repr__(self):
        return '<BadQueryException {} {}>'.format(self.query, self.error)

class ElasticSearchEndpoint(object):
    def __init__(self, store, index=None):
        if isinstance(store, Store):
            store = store.slug
        if isinstance(index, Index):
            index = index.slug
        self.store, self.index = store, index
    
    @property
    def search_url(self):
        if self.index:
            path = '/{0}/{1}/_search'.format(self.store, self.index)
        else:
            path = '/{0}/_search'.format(self.store)
        return urllib.parse.urlunsplit(('http',
                                        '{host}:{port}'.format(**settings.ELASTICSEARCH_SERVER),
                                        path, '', ''))

    def query(self, query):
        logger.debug("Query: %s", query)
        request = urllib.request.Request(self.search_url, json.dumps(query).encode())
        request.add_header("User-Agent", USER_AGENTS['agent'])
        try:
            response = json.load(urllib.request.urlopen(request))
        except urllib.request.HTTPError as e:
            if e.code == http.client.BAD_REQUEST:
                raise BadQueryException(query, json.load(e)) from e
            raise
        logger.debug("Query returned %d hits: %s", response['hits']['total'], query)
        return response
