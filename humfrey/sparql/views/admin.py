from django.conf import settings
from django.core.exceptions import PermissionDenied
from django_conneg.views import HTMLView, JSONView

from .core import StoreView, QueryView
from humfrey.linkeddata.resource import ResourceRegistry
from humfrey.linkeddata.views import MappingView
from humfrey.desc import views as desc_views
from humfrey.sparql.models import Store

class IndexView(HTMLView, JSONView):
    def get(self, request):
        stores = Store.objects.all().order_by('name')
        if not request.user.is_superuser:
            stores = [s for s in stores if request.user.has_any_perms(s)]
        context = {'stores': stores}
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
else:
    SearchView = None