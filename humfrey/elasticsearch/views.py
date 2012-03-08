import json
import math
import urllib
import urllib2
import urlparse

from django.conf import settings
from django_conneg.views import HTMLView, JSONPView

from .forms import SearchForm


class SearchView(HTMLView, JSONPView):
    index_name = 'search'
    page_size = 10

    class Deunderscorer(object):
        def __init__(self, obj):
            self.obj = obj
        def __getitem__(self, key):
            try:
                value = self.obj[key]
            except KeyError:
                value = self.obj['_' + key]
            if isinstance(value, (dict, list)):
                value = SearchView.Deunderscorer(value)
            return value
        def __setitem__(self, key, value):
            self.obj[key] = value
        def __getattribute__(self, name):
            if name == 'obj':
                return super(SearchView.Deunderscorer, self).__getattribute__(name)
            return getattr(self.obj, name)
        def __len__(self):
            return len(self.obj)
        def __repr__(self):
            return repr(self.obj)
                
    def get(self, request):
        form = SearchForm(request.GET or None)
        context = {'form': form}
        
        if form.is_valid():
            context.update(self.get_results(form.cleaned_data))

        return self.render(request, context, 'elasticsearch/search')
    
    def get_results(self, cleaned_data):
        page = cleaned_data.get('page') or 1
        start = (page - 1) * self.page_size
        url = urlparse.urlunsplit(('http',
                                   '%s:%d' % (settings.ELASTICSEARCH_SERVER['host'], settings.ELASTICSEARCH_SERVER['port']),
                                   '/%s/_search' % self.index_name,
                                   '',
                                   ''))

        query = {
            'query': {'query_string': {'query': cleaned_data['q']}},
            'from': start,
        }

        response = urllib2.urlopen(url, json.dumps(query))
        results = self.Deunderscorer(json.load(response))

        results.update(self.get_pagination(page, start, results))
        results['q'] = cleaned_data['q']

        return results

    def get_pagination(self, page, start, results):
        page_count = int(math.ceil(results['hits']['total'] / 10.0))
        pages = set([1, page_count])
        pages.update(p for p in range(page-5, page+6) if 1 <= p <= page_count)
        pages = sorted(pages)
        
        pages_out = []
        for p in pages:
            if pages_out and pages_out[-1] != p - 1:
                pages_out.append(None)
            pages_out.append(p)
        
        return {'page_count': page_count,
                'start': start + 1,
                'pages': pages_out,
                'page': page}
