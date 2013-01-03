try:
    import simplejson as json
except ImportError:
    import json
import logging
import urllib2
import urlparse

from django.conf import settings

from humfrey.sparql.models import Store
from humfrey.elasticsearch.models import Index
from humfrey.update.tasks.retrieve import USER_AGENTS

logger = logging.getLogger(__name__)

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
        return urlparse.urlunsplit(('http',
                                    '{host}:{port}'.format(**settings.ELASTICSEARCH_SERVER),
                                    path, '', ''))

    def query(self, query):
        request = urllib2.Request(self.search_url, json.dumps(query))
        request.add_header("User-Agent", USER_AGENTS['agent'])
        response = json.load(urllib2.urlopen(request))
        logger.debug("Query returned %d hits: %s", response['hits']['total'], query)
        return response
