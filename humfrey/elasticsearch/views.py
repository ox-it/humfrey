from __future__ import division

import collections
import copy
import json
import math
import urllib
import urllib2
import urlparse

from django.conf import settings
from django_conneg.decorators import renderer
from django_conneg.http import HttpResponseSeeOther
from django_conneg.views import HTMLView, JSONPView, ErrorCatchingView
from rdflib import URIRef

from humfrey.sparql.views import StoreView
from humfrey.sparql.utils import get_labels
from humfrey.utils.namespaces import expand, contract
from humfrey.linkeddata.uri import doc_forwards
from humfrey.linkeddata.views import MappingView

from .forms import SearchForm


class SearchView(HTMLView, JSONPView, MappingView, ErrorCatchingView, StoreView):
    index_name = 'public'
    page_size = 10

    # e.g. {'filter.category.uri': ('filter.subcategory.uri',)}
    dependent_parameters = {}

    facets = {'type': {'terms': {'field': 'type.uri',
                                          'size': 20}}}
    template_name = 'elasticsearch/search'
    
    class MissingQuery(Exception):
        pass

    class Deunderscorer(object):
        def __init__(self, obj):
            self.obj = obj
        def __getitem__(self, key):
            try:
                value = self.obj[key]
            except KeyError:
                try:
                    value = self.obj['_' + key]
                except KeyError:
                    return None
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
        context = {'form': form,
                   'base_url': request.build_absolute_uri(),
                   'renderers': [{'name': r.name,
                                  'format': r.format,
                                  'mimetypes': r.mimetypes} for r in self._renderers],
                   'dependent_parameters': self.dependent_parameters}
        
        if form.is_valid():
            context.update(self.get_results(dict((k, request.GET[k]) for k in request.GET),
                                            form.cleaned_data))
            if context['page'] > context['page_count']:
                query = copy.copy(request.GET)
                query['page'] = context['page_count']
                query = urllib.urlencode(query)
                return HttpResponseSeeOther('{path}?{query}'.format(path=request.path,
                                                                    query=query))

        context = self.finalize_context(request, context)


        return self.render(request, context, self.template_name)

    def finalize_context(self, request, context):
        return context
    
    @property
    def search_url(self):
        return urlparse.urlunsplit(('http',
                                    '{host}:{port}'.format(**settings.ELASTICSEARCH_SERVER),
                                    '/%s/_search' % self.index_name,
                                    '',
                                    ''))

    def get_results(self, parameters, cleaned_data):
        page = cleaned_data.get('page') or 1
        page_size = cleaned_data.get('page_size') or self.page_size
        start = (page - 1) * page_size

        query = {
            'query': {'query_string': {'query': cleaned_data['q'],
                                       'default_operator': 'AND'}},
            'from': start,
            'size': page_size,
            # A blank conjunctive filter. We'll remove this later if necessary.
            'filter': {'and': []},
        }

        # Parse query parameters of the form 'filter.FIELDNAME'.
        for key in list(parameters):
            parameter = parameters[key]
            if key.startswith('filter.'):
                if not parameter:
                    del parameters[key]
                    continue
                elif parameter == '-':
                    filter = {'missing': {'field': key[7:]}}
                else:
                    if key.endswith('.uri') and ':' in parameter:
                        parameter = expand(parameter)
                    filter = {'term': {key[7:]: parameter}}
                query['filter']['and'].append(filter)

        # If there aren't any filters defined, we don't want a filter part of
        # our query.
        if not query['filter']['and']:
            del query['filter']['and']
        if not query['filter']:
            del query['filter']

        if self.facets:
            # Copy the facet definitions as we'll be playing with them shortly.
            facets = copy.deepcopy(self.facets)

            # Add facet filters for all active filters except any acting on this
            # particular facet.
            if 'filter' in query:
                for facet in facets.itervalues():
                    for filter in query['filter']['and']:
                        if facet['terms']['field'] not in (filter.get('term') or filter['missing']):
                            if 'facet_filter' not in facet:
                                facet['facet_filter'] = {'and': []}
                            facet['facet_filter']['and'].append(filter)
            query['facets'] = facets

        response = urllib2.urlopen(self.search_url, json.dumps(query))
        results = self.Deunderscorer(json.load(response))

        results.update(self.get_pagination(page_size, page, start, results))
        results['q'] = cleaned_data['q']

        facet_labels = set()
        for key in query['facets']:
            meta = results['facets'][key]['meta'] = query['facets'][key]
            filter_value = parameters.get('filter.%s' % query['facets'][key]['terms']['field'])
            results['facets'][key]['filter'] = {'present': filter_value is not None,
                                                'value': filter_value}
            if meta['terms']['field'].endswith('.uri'):
                for term in results['facets'][key]['terms']:
                    facet_labels.add(term['term'])
                    term['value'] = contract(term['term'])
            else:
                for term in results['facets'][key]['terms']:
                    term['value'] = term['term']
        
        labels = get_labels(facet_labels, endpoint=self.endpoint)
        for key in query['facets']:
            if results['facets'][key]['meta']['terms']['field'].endswith('.uri'):
                for term in results['facets'][key]['terms']:
                    uri = URIRef(term['term'])
                    if uri in labels:
                        term['label'] = unicode(labels[uri])

        for hit in results['hits']['hits']:
            try:
                hit['_url'] = doc_forwards(hit['_source']['uri'])[None]
            except KeyError:
                raise

        return results

    def get_pagination(self, page_size, page, start, results):
        page_count = int(math.ceil(results['hits']['total'] / page_size))
        pages = set([1, page_count])
        pages.update(p for p in range(page-5, page+6) if 1 <= p <= page_count)
        pages = sorted(pages)
        
        pages_out = []
        for p in pages:
            if pages_out and pages_out[-1] != p - 1:
                pages_out.append(None)
            pages_out.append(p)
        
        return {'page_count': max(1, page_count),
                'start': start + 1,
                'pages': pages_out,
                'page': page}

    @renderer(format="autocomplete", name="Autocomplete JSON")
    def render_autocomplete(self, request, context, template_name):
        if not context.get('hits'):
            raise self.MissingQuery()
        context = {'items': [{'id': hit['_source']['uri'],
                              'name': hit['_source']['label'],
                              'altNames': '\t'.join(l for l in hit['_source'].get('altLabel', []) + hit['_source'].get('hiddenLabel', []))} for hit in context['hits']['hits']]}
        return self.render_to_format(request, context, template_name, 'json')

    def error(self, request, exception, args, kwargs, status_code):
        if isinstance(exception, self.MissingQuery):
            return self.error_view(request,
                                   {'error': {'status_code': 400,
                                              'message': "Missing 'q' parameter."}},
                                   'elasticsearch/bad_request')
        else:
            return super(SearchView, self).error(request, exception, args, kwargs, status_code)
