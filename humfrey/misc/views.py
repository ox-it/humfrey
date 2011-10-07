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
        template_name = 'index'
        rss_url = None

        def initial_context(self, request):
            try:
                feed = feedparser.parse(self.rss_url)
                for entry in feed.entries:
                    entry.updated_datetime = datetime.datetime(*entry.updated_parsed[:6] + (pytz.utc,)) \
                                                 .astimezone(pytz.timezone(settings.TIME_ZONE))
            except Exception, e:
                feed = None
            return {
                'feed': feed,
            }

        def get(self, request):
            context = self.initial_context(request)
            return self.render(request, context, self.template_name)


class SimpleView(HTMLView, CachedView):
    context = {}
    template_name = None

    def get(self, request):
        return self.render(request, self.context.copy(), self.template_name)
