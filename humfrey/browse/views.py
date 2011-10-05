from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import Http404

from django_conneg.views import HTMLView, JSONView
from humfrey.results.views.standard import RDFView
from humfrey.utils.views import CachedView, RedisView

class IndexView(RedisView, HTMLView, JSONView, RDFView, CachedView):
    LIST_META = 'humfrey:browse:list-meta:all'

    def get(self, request):
        client = self.get_redis_client()
        lists = self.unpack(client.get(self.LIST_META))

        context = {
            'lists': lists,
        }
        return self.render(request, context, 'browse/index')

class ListView(RedisView, HTMLView, JSONView, RDFView, CachedView):
    LIST_META = 'humfrey:browse:list-meta:individual'
    LIST_ITEMS = 'humfrey:browse:list:%s:%s'

    class RedisWrapper(object):
        def __init__(self, client, id, field):
            self.client, self.key = client, ListView.LIST_ITEMS % (id, field)
        def __len__(self):
            return self.client.llen(self.key)
        def __getitem__(self, key):
            if isinstance(key, slice):
                return map(ListView.unpack, self.client.lrange(self.key, key.start, key.stop - 1))
            else:
                return ListView.unpack(self.client.lindex(key))

    def get(self, request, id):
        client = self.get_redis_client()
        meta = client.hget(self.LIST_META, id)
        if not meta:
            raise Http404
        meta = self.unpack(meta)

        paginator = Paginator(self.RedisWrapper(client, id, 'uri'), 100)

        page = request.GET.get('_page') or "1"
        try:
            results = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            raise Http404

        context = {
            'meta': meta,
            'paginator': paginator,
            'page': page,
            'results': results,
        }

        return self.render(request, context, 'browse/list')

