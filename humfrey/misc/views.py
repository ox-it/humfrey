import datetime

from django.conf import settings

from django_conneg.views import HTMLView

from humfrey.utils.views import CachedView

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
        def initial_context(self, request, rss_url, template='index'):
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries:
                    entry.updated_datetime = datetime.datetime(*entry.updated_parsed[:6]+(pytz.utc,)) \
                                                 .astimezone(pytz.timezone(settings.TIME_ZONE))
            except Exception, e:
                feed = None
            return {
                'feed': feed,
            }
    
        def get(self, request, rss_url, template='index'):
            context = self.initial_context(request, rss_url, template)

            # So we match the syntax for other views taking a template
            # parameter.
            if template.endswith('.html'):
                template = template[:-5]
            return self.render(request, context, 'index')


class SimpleView(HTMLView, CachedView):
    context = None
    template_name = None
    
    def get(self, request):
        return self.render(request, self.context.copy(), self.template_name)
        