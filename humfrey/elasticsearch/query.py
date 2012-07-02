try:
    import json
except ImportError:
    import simplejson as json
import urllib2
import urlparse

from django.conf import settings

from humfrey.sparql.models import Store
from humfrey.elasticsearch.models import Index
from humfrey.update.tasks.retrieve import USER_AGENTS

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
        response = urllib2.urlopen(request)
        return json.load(response)