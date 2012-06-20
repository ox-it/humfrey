from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django_conneg.views import HTMLView, JSONView

from .core import StoreView, QueryView
from humfrey.linkeddata.resource import ResourceRegistry
from humfrey.linkeddata.views import MappingView
from humfrey.desc import views as desc_views
from humfrey.misc import views as misc_views
from humfrey.sparql.views import StoreView
from humfrey.sparql.models import Store

class IndexView(HTMLView, JSONView):
    def get(self, request):
        stores = Store.objects.all().order_by('name')
        if not request.user.has_perm('sparql.query_store'):
            stores = [s for s in stores if s.can_query(request.user)]
        context = {'stores': stores,
                   'with_elasticsearch': 'humfrey.elasticsearch' in settings.INSTALLED_APPS}
        return self.render(request, context, 'sparql/index')

class StoreChooseMixin(object):
    @property
    def doc_view(self):
        return ('admin', 'sparql-admin:view',
                (), {},
                (), {'store': self.store_name})
    desc_view = doc_view

    id_mapping = ()
    resource_registry = ResourceRegistry()
    
    def dispatch(self, request, *args, **kwargs):
        self.store_name = kwargs.pop('store')
        if not self.store.can_query(request.user):
            raise PermissionDenied
        return super(StoreChooseMixin, self).dispatch(request, *args, **kwargs)
        
class DocView(StoreChooseMixin, desc_views.DocView):
    pass

class QueryView(StoreChooseMixin, QueryView):
    pass

if 'humfrey.elasticsearch' in settings.INSTALLED_APPS:
    from humfrey.elasticsearch import views as elasticsearch_views

    class SearchView(StoreChooseMixin, elasticsearch_views.SearchView):
        pass

    class ElasticSearchPassThroughView(StoreChooseMixin, StoreView, misc_views.PassThroughView):
        def get_target_url(self, request, index=None):
            params = {'host': settings.ELASTICSEARCH_SERVER['host'],
                      'port': settings.ELASTICSEARCH_SERVER['port'],
                      'store': self.store_name,
                      'index': index}
            if index:
                url = 'http://{host}:{port}/{store}/{index}/_search'.format(**params)
            else:
                url = 'http://{host}:{port}/{store}/_search'.format(**params)
            if request.META.get('QUERY_STRING'):
                url += '?' + request.META['QUERY_STRING']
            return url
        def process_response(self, request, response, index=None):
            response['X-URI-Lookup'] = reverse('sparql-admin:view', args=[self.store_name]) + '?uri='
            response['X-SPARQL-Endpoint'] = reverse('sparql-admin:query', args=[self.store_name])
            return response

else:
    SearchView = None
    ElasticSearchPassThroughView = None
