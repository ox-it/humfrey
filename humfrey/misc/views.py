import datetime
import httplib
import urlparse
import wsgiref.util

from django.conf import settings
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
        for name, value in request.META.iteritems():
            if name in ('CONTENT_TYPE', 'CONTENT_LENGTH') and value:
                pass # Good
            elif name in ('HTTP_HOST', 'HTTP_CONNECTION', 'HTTP_COOKIE', 'HTTP_ACCEPT_ENCODING'):
                continue # Bad
            elif name.startswith('HTTP_'):
                name = name[5:] # Good (minus the 'HTTP_')
            else:
                continue
            headers[name.capitalize().replace('_', '-')] = value
        return headers

    def process_response(self, request, response, *args, **kwargs):
        return response

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
        conn.putrequest(method=self.get_method(request, *args, **kwargs),
                        url=path)
        for k, v in self.get_headers(request, *args, **kwargs).iteritems():
            conn.putheader(k, v)
        conn.endheaders()
        conn.send(request.raw_post_data)

        http_response = conn.getresponse()
        
        # Wrap the httplib.HTTPResponse object in an iterator
        def response_body():
            chunk = http_response.read(4096)
            while chunk:
                yield chunk
                chunk = http_response.read(4096)
            http_response.close()

        response = HttpResponse(response_body())
        response.status_code = http_response.status
        for key, value in http_response.getheaders():
            if not wsgiref.util.is_hop_by_hop(key):
                response[key] = value
        
        response = self.process_response(request, response, *args, **kwargs)

        return response
    post = put = delete = get
        
