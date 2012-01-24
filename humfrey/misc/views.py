import datetime

import rdflib
from django.conf import settings

from django_conneg.views import HTMLView

from humfrey.utils.views import CachedView, EndpointView
from humfrey.utils.sparql import SparqlResultList, SparqlResultBool, SparqlResultGraph

# Only create FeedView class if feedparser and pytz are importable.
# This will make feedparser and pytz optional dependencies if one
# doesn't want to use FeedView.
try:
    import feedparser
    import pytz
except ImportError, e:
    pass
else:
    class FeedView(HTMLView, CachedView):
        rss_url = None
        template_name = None

        def get_feed(self):
            try:
                feed = feedparser.parse(self.rss_url)
                for entry in feed.entries:
                    entry.updated_datetime = datetime.datetime(*entry.updated_parsed[:6]).replace(tzinfo=pytz.utc) \
                                                 .astimezone(pytz.timezone(settings.TIME_ZONE))
            except Exception, e:
                feed = None
            return feed
    
        def get(self, request):
            context = {'feed': self.get_feed()}

            # So we match the syntax for other views taking a template
            # parameter.
            template_name = self.template_name
            if template_name.endswith('.html'):
                template_name = template_name[:-5]
            return self.render(request, context, 'index')


class SimpleView(HTMLView, CachedView):
    context = {}
    template_name = None

    def get(self, request):
        return self.render(request, self.context.copy(), self.template_name)

class CannedQueryView(CachedView, EndpointView):
    query = None
    template_name = None

    def get_query(self, request, *args, **kwargs):
        return self.query

    def get_locations(self, request, *args, **kwargs):
        """
        Override to provide the canonical and format-specific locations for this resource.
        
        Example return value: ('http://example.com/data', 'http://example.org/data.rss')
        """
        return None, None

    def get(self, request, *args, **kwargs):
        self.base_location, self.content_location = self.get_locations(request, *args, **kwargs)
        query = self.get_query(request, *args, **kwargs)
        result = self.endpoint.query(query)
        if isinstance(result, SparqlResultList):
            context = {'results': result}
        elif isinstance(result, SparqlResultBool):
            context = {'result': result}
        elif isinstance(result, SparqlResultGraph):
            context = {'graph': result}

        if self.content_location:
            context['additional_headers'] = {'Content-location': self.content_location}

        if 'format' in kwargs:
            self.render_to_format(request, context, self.template_name, kwargs['format'])
        else:
            return self.render(request, context, self.template_name)
