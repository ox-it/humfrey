from django.http import Http404
from django_conneg.views import ContentNegotiatedView, HTMLView, JSONPView
from humfrey.linkeddata.views import MappingView
from humfrey.sparql.views import StoreView

from . import config

def _get_feed_or_404(slug):
    try:
        return config.FEEDS[slug]
    except KeyError:
        raise Http404

class IndexView(HTMLView, JSONPView):
    template_name = 'feeds/index'

    def get(self, request):
        feeds = config.FEED_META.values()
        feeds.sort(key=lambda f: f['name'])
        self.context.update({'feeds':feeds})
        return self.render()

class FeedView(HTMLView, StoreView, MappingView):
    pass

class FeedConfigView(FeedView):
    template_name = 'feeds/config'

    def get(self, request, slug):
        feed = _get_feed_or_404(slug)

        form = feed.form_class(request.GET or None,
                               conneg=feed.conneg,
                               endpoint=self.endpoint,
                               orderings=feed.orderings)

        self.context.update({'feed': feed.meta,
                             'form': form})

        return self.render()

class FeedRenderView(ContentNegotiatedView):
    def dispatch(self, request, slug):
        feed = _get_feed_or_404(slug)
        return feed(request)
