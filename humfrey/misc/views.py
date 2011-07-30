import datetime

from django.conf import settings

from humfrey.utils.views import BaseView
from humfrey.utils.cache import cached_view

# Only create FeedView class if feedparser and pytz are importable.
# This will make feedparser and pytz optional dependencies if one
# doesn't want to use FeedView.
try:
    import feedparser
    import pytz
except ImportError, e:
    pass
else:
    class FeedView(BaseView):
        def initial_context(self, request, rss_url, template='index'):
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries:
                    entry.updated_datetime = datetime.datetime(*entry.updated_parsed[:6], tzinfo=pytz.utc) \
                                                 .astimezone(pytz.timezone(settings.TIME_ZONE))
            except Exception, e:
                feed = None
            return {
                'feed': feed,
            }
    
        @cached_view
        def handle_GET(self, request, context, rss_url, template='index'):
            # So we match the syntax for other views taking a template
            # parameter.
            if template.endswith('.html'):
                template = template[:-5]
            return self.render(request, context, 'index')