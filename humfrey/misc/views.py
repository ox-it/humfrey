import datetime
import httplib
import urlparse

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.views.generic import View
from django_conneg.views import HTMLView


# Only create FeedView class if feedparser and pytz are importable.
# This will make feedparser and pytz optional dependencies if one
# doesn't want to use FeedView.
try:
    import feedparser
    import pytz
except ImportError, e:
    pass
else:
    class FeedView(HTMLView):
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


class SimpleView(HTMLView):
    context = {}
    template_name = None

    def get(self, request):
        return self.render(request, self.context.copy(), self.template_name)

class PassThroughView(View):
    def get_target_url(self, request, *args, **kwargs):
        raise NotImplementedError
    def get_method(self, request, *args, **kwargs):
        return request.method
    def get_headers(self, request, *args, **kwargs):
        headers = {}
        for name in request.META:
            if name.startswith('HTTP_'):
                headers[name[5:].capitalize().replace('_', '-')] = request.META[name]
        return headers

    def get(self, request, *args, **kwargs):
        url = self.get_target_url(request, *args, **kwargs)
        url = urlparse.urlparse(url)
        
        if ':' in url.netloc:
            host, port = url.netloc.split(':', 1)
            port = int(port)
        else:
            host, port = url.netloc, {'http': 80, 'https': 443}[url.scheme]
        path = urlparse.urlunparse(url._replace(scheme='', netloc=''))

        connection_class = httplib.HTTPConnection if url.scheme == 'http' else httplib.HTTPSConnection

        conn = connection_class(host=host, port=port)
        conn.request(method=self.get_method(request, *args, **kwargs),
                     url=path,
                     body=request,
                     headers=self.get_headers(request, *args, **kwargs))
        
        http_response = conn.getresponse()
        
        response = HttpResponse(http_response.fp)
        response.status_code = http_response.status
        for key, value in http_response.getheaders():
            response[key] = value
        return response
        
        