"""
Implementation of the OpenSearch specification for humfrey's ElasticSearch integration.

http://www.opensearch.org/Specifications/OpenSearch/1.1
"""

import datetime
import hashlib
import urllib
import urlparse

from django.conf import settings
from django.http import HttpResponse
from lxml import etree
from lxml.builder import ElementMaker
import pytz

from django_conneg.conneg import Conneg
from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView

namespaces = {
    'atom': 'http://www.w3.org/2005/Atom',
    'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
    'xhtml': 'http://www.w3.org/1999/xhtml',
}

ATOM = ElementMaker(namespace=namespaces['atom'], nsmap=namespaces)
OPENSEARCH = ElementMaker(namespace=namespaces['opensearch'], nsmap=namespaces)

class OpenSearchDescriptionView(ContentNegotiatedView):
    _default_format = 'opensearchdescription'

    def get(self, request, search_view):
        self.search_view = search_view
        return self.render()

    @renderer(format='opensearchdescription', mimetypes=('application/opensearchdescription+xml',), name='OpenSearch Description')
    def render_opensearchdescription(self, request, context, template_name):
        description = OPENSEARCH.OpenSearchDescription()

        meta = OpenSearchView.opensearch_meta.copy()
        meta.update(self.search_view.opensearch_meta)
        for key, value in meta.iteritems():
            if value is not None:
                description.append(OPENSEARCH(key, value))

        for image in self.search_view.opensearch_images:
            description.append(OPENSEARCH.Image(image['url'],
                                                height=unicode(image.get('height', 16)),
                                                width=unicode(image.get('width', 16)),
                                                type=unicode(image.get('type' ,'image/x-icon'))))

        for renderer in Conneg(obj=self.search_view).renderers:
            template = request.build_absolute_uri('?') + '?q={searchTerms}&page={startPage?}&format='+renderer.format
            for mimetype in renderer.mimetypes:
                url = OPENSEARCH.Url(type=mimetype.value,
                                     template=template,
                                     rel='results')
                description.append(url)

        return HttpResponse(etree.tostring(description, pretty_print=True, xml_declaration=True),
                            mimetype='application/xml')

class OpenSearchView(ContentNegotiatedView):
    opensearch_meta = {'ShortName': 'Search',
                       'LongName': 'Search',
                       'Description': None,
                       'Tags': None,
                       'Contact': None,
                       'Developer': None,
                       'Attribution': None,
                       'SyndicationRight': 'limited',
                       'AdultContent': 'false',
                       'Language': getattr(settings, 'LANGUAGE', 'en')}
    opensearch_images = []
    opensearch_feed_title_template = 'Search: {0}'
    
    opensearchdescription_view = staticmethod(OpenSearchDescriptionView.as_view())
    
    def dispatch(self, request):
        if request.GET.get('opensearchdescription') == '':
            return self.opensearchdescription_view(request, self)
        return super(OpenSearchView, self).dispatch(request)
    
    def munge_query_parameter(self, request, clear=False, **updates):
        url = request.build_absolute_uri()
        query = urlparse.parse_qsl(urlparse.urlparse(url).query, True)
        query = dict((k, v) for k, v in query)
        for key, value in updates.iteritems():
            if value is None:
                query.pop(key, None)
            else:
                query[key] = value
        query = sorted(query.iteritems())
        return urlparse.urljoin(url, '?' + urllib.urlencode(query))
    
    def atom_navigation_link(self, request, rel, page):
        return ATOM.link(rel=rel,
                         href=self.munge_query_parameter(request, page=unicode(page)),
                         type='application/atom+xml')

    @renderer(format='atom', mimetypes=('application/atom+xml',), name='Atom')
    def render_atom(self, request, context, template_name):
        if 'hits' not in context:
            return NotImplemented

        updated = pytz.utc.localize(datetime.datetime.utcnow()).isoformat()

        feed = ATOM.feed(
            ATOM.title(self.opensearch_feed_title_template.format(context['q'])),
            ATOM.updated(updated),
            OPENSEARCH.totalResults(unicode(context['hits']['total'])),
            OPENSEARCH.startIndex(unicode(context['start'])),
            OPENSEARCH.itemsPerPage(unicode(context['page_size'])),
            OPENSEARCH.Query(role='request', searchTerms=context['q'], startPage=unicode(context['page'])),
        )

        # atom:link elements
        for renderer in context['renderers']:
            for mimetype in renderer['mimetypes']:
                feed.append(ATOM.link(rel='alternate',
                                      href=request.build_absolute_uri(renderer['url']),
                                      type=mimetype))
        feed.append(self.atom_navigation_link(request, rel='self', page=context['page']))
        feed.append(self.atom_navigation_link(request, rel='first', page=1))
        if context['page'] > 1:
            feed.append(self.atom_navigation_link(request, rel='previous', page=context['page']-1))
        if context['page'] < context['page_count']:
            feed.append(self.atom_navigation_link(request, rel='next', page=context['page']+1))
        feed.append(self.atom_navigation_link(request, rel='last', page=context['page_count']))
        feed.append(ATOM.link(rel='search',
                              href=urlparse.urljoin(request.build_absolute_uri(), '?opensearchdescription'),
                              type='application/opensearchdescription+xml',
                              title=self.opensearch_meta.get('LongName', 'Search')))

        for hit in context['hits']['hits']:
            source = hit['_source']
            entry = ATOM.entry(
                ATOM.title(source.get('label', '')),
                ATOM.link(request.build_absolute_uri(hit['_url'])),
                ATOM.updated(updated), # For want of something better
            )
            if 'uri' in source:
                entry.append(ATOM.id(source['uri']))
            else:
                entry.append(ATOM.id('urn:sha1:' + hashlib.sha1('/'.join((hit['_index'], hit['_type'], hit['_id']))).hexdigest())),
            if 'description' in source:
                description, description_type = source['description'], 'text'
                if description[:5].lower() == '<div>' and description[-6:].lower() == '</div>':
                    description_type = 'html'
                try:
                    description = etree.fromstring(description)
                except:
                    pass
                else:
                    description_type = 'xhtml' if description.tag == '{http://www.w3.org/1999/xhtml}div' else 'application/xml'
                entry.append(ATOM.content(description, type=description_type)),
            feed.append(entry)
        
        return HttpResponse(etree.tostring(feed, pretty_print=True, xml_declaration=True),
                            mimetype='application/atom+xml')