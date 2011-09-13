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
    context = None
    template_name = None
    
    def get(self, request):
        return self.render(request, self.context, self.template_name)
        