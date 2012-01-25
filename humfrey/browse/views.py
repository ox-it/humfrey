from django.core.paginator import Page, Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.http import Http404

import rdflib
from django_conneg.views import HTMLView, JSONView, JSONPView
from humfrey.linkeddata.uri import doc_forward
from humfrey.results.views.standard import RDFView
from humfrey.utils.views import RedisView

class IndexView(RedisView, HTMLView, JSONPView):
    LIST_META = 'humfrey:browse:list-meta:all'

    def get(self, request):
        client = self.get_redis_client()
        lists = self.unpack(client.get(self.LIST_META))

        context = {
            'lists': lists,
        }
        return self.render(request, context, 'browse/index')

class ListView(RedisView, HTMLView, JSONPView):
    LIST_META = 'humfrey:browse:list-meta:individual'
    LIST_ITEMS = 'humfrey:browse:list:%s:%s'

    _json_indent = 2

    class RedisWrapper(object):
        def __init__(self, client, id, field, reverse):
            self.client, self.key = client, ListView.LIST_ITEMS % (id, field)
            self.reverse = reverse
        def __len__(self):
            return self.client.llen(self.key)
        def __getitem__(self, key):
            if not self.reverse:
                if isinstance(key, slice):
                    return map(ListView.unpack, self.client.lrange(self.key, key.start, key.stop - 1))
                else:
                    return ListView.unpack(self.client.lindex(key))
            else:
                length = len(self)
                if isinstance(key, slice):
                    return reversed(map(ListView.unpack, self.client.lrange(self.key, length - key.stop, length - key.start - 1)))
                else:
                    return ListView.unpack(self.client.lindex(length - key - 1))

    def get(self, request, id):
        client = self.get_redis_client()
        meta = client.hget(self.LIST_META, id)
        if not meta:
            raise Http404
        meta = self.unpack(meta)
        meta['per_page'] = meta.get('per_page') or 100
        
        sort_text = request.GET.get('_sort', meta['initial_sort'])
        if sort_text and sort_text.startswith('-'):
            sort, reverse_list = sort_text[1:], True
        else:
            sort, reverse_list = sort_text, False
        if sort and sort not in meta['fields']:
            raise Http404

        paginator = Paginator(self.RedisWrapper(client, id, sort, reverse_list), meta['per_page'])

        page = request.GET.get('_page') or "1"
        try:
            page = int(page)
            result = paginator.page(page)
        except (ValueError, PageNotAnInteger, EmptyPage):
            raise Http404

        formats = {}
        for renderer in self._renderers:
            formats[renderer.format] = {'url': '%s?_sort=%s&_page=%d&format=%s' % (reverse('browse:list', args=[id]), sort_text, page, renderer.format),
                                        'format': renderer.format,
                                        'name': renderer.name,
                                        'mimetypes': renderer.mimetypes}

        context = {
            'meta': meta,
            'paginator': paginator,
            'page': page,
            'result': result,
            'sortText': sort_text,
            'sort': sort,
            'reverse': reverse_list,
            'formats': formats.values(),
        }

        renderers = self.get_renderers(request)
        if renderers:
            context['additional_headers'] = {'Content-location': request.build_absolute_uri(formats[renderers[0].format]['url'])}

        return self.render(request, context, meta.pop('template_name'))

    def preprocess_context_for_json(self, context):
        context['result'].meta = context.pop('meta')
        del context['page']
        del context['sortText']
        del context['sort']
        del context['reverse']
        return context

    def simplify(self, value):
        if isinstance(value, Paginator):
            return NotImplemented
        elif isinstance(value, rdflib.Literal):
            return value.toPython()
        elif isinstance(value, (rdflib.URIRef, rdflib.BNode)):
            return unicode(value)
        elif isinstance(value, dict) and 'uri' in value:
            new_value = {}
            for k, v in value.iteritems():
                new_value[k] = self.simplify(v)
            new_value['_about'] = new_value.pop('uri')
            if new_value['_about']:
                new_value['_seeAlso'] = doc_forward(new_value['_about'])
            return new_value
        elif isinstance(value, Page):
            base_url = self.request.build_absolute_uri(reverse('browse:list', args=[self.kwargs['id']]))
            result = {
                "_about": "%s?_page=%d" % (base_url, value.number),
                "partOf": base_url,
                "first": "%s?_page=%d" % (base_url, 1),
                "page": value.number,
                "pageSize": value.meta['per_page'],
                "contains": map(self.simplify, value.object_list),
            }
            if value.has_next():
                result['next'] = "%s?_page=%d" % (base_url, value.next_page_number())
            return result
        else:
            return super(ListView, self).simplify(value)
