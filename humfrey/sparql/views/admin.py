import urllib.request, urllib.parse, urllib.error

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django_conneg.views import ContentNegotiatedView, HTMLView, JSONView

from humfrey.linkeddata.resource import ResourceRegistry
from humfrey.linkeddata.views import MappingView
from humfrey.desc import views as desc_views
from humfrey.misc import views as misc_views
from humfrey.results.views.standard import RDFView
from humfrey.sparql.views import StoreView, QueryView, CannedQueryView
from humfrey.sparql.models import Store
from humfrey.utils.namespaces import NS

class IndexView(HTMLView, JSONView):
    def get(self, request):
        stores = Store.objects.all().order_by('name')
        if not request.user.has_perm('sparql.query_store'):
            stores = [s for s in stores if request.user.has_perm('sparql.query_store', s)]
        context = {'stores': stores,
                   'with_elasticsearch': 'humfrey.elasticsearch' in settings.INSTALLED_APPS}
        return self.render(request, context, 'sparql/index')

class StoreChooseMixin(object):
    @property
    def doc_view(self):
        return reverse('sparql-admin:view', kwargs={'store': self.store_name})
    desc_view = doc_view

    id_mapping = ()
    resource_registry = ResourceRegistry()

    # These are sensible defaults.
    permission_requirements = {'get': 'sparql.query_store',
                               'post': 'sparql.update_store',
                               'put': 'sparql.update_store',
                               'delete': 'sparql.delete_store',
                               'head': 'sparql.query_store'}

    def dispatch(self, request, *args, **kwargs):
        self.store_name = kwargs.pop('store')
        method = request.method.lower()
        if not hasattr(self, method):
            pass
        if method in self.permission_requirements:
            perm = self.permission_requirements[method]
            if not request.user.has_perm(perm) and \
               not request.user.has_perm(perm, self.store):
                setattr(self, method, self.not_authorized)
        elif method != 'options':
            setattr(self, method, self.not_authorized)
        return super(StoreChooseMixin, self).dispatch(request, *args, **kwargs)

    def not_authorized(self, request):
        if request.user.is_authenticated():
            raise PermissionDenied
        else:
            return login_required(lambda request:None)(request)


class DocView(StoreChooseMixin, desc_views.DocView):
    check_canonical = False

    @property
    def sparql_view_url(self):
        return reverse('sparql-admin:query', kwargs={'store': self.kwargs['store']})


class QueryView(StoreChooseMixin, QueryView):
    permission_requirements = {'get': 'sparql.query_store',
                               'post': 'sparql.query_store',
                               'head': 'sparql.query_store'}

class GraphDataView(StoreChooseMixin, StoreView, misc_views.PassThroughView):
    def get_target_url(self, request):
        return "{0}?{1}".format(self.store.graph_store_endpoint,
                                urllib.parse.urlencode({'graph': request.GET['graph']}))

    def post(self, request, *args, **kwargs):
        return super(GraphDataView, self).get(request, *args, **kwargs)

class GraphListView(StoreChooseMixin, CannedQueryView, RDFView, HTMLView, MappingView):
    query = """
        CONSTRUCT {
         ?g a sd:Graph ;
           dcterms:publisher ?publisher ;
           dcterms:license ?license ;
           dcterms:created ?created ;
           dcterms:modified ?modified
        } WHERE {
          {
            SELECT DISTINCT ?g {
              GRAPH ?g { }
            }
          }
          OPTIONAL { ?g rdfs:label ?label } .
          OPTIONAL { ?g dcterms:publisher ?publisher } .
          OPTIONAL { ?g dcterms:license ?license } .
          OPTIONAL { ?g dcterms:created ?created } .
          OPTIONAL { ?g dcterms:modified ?modified } .
        }
    """

    template_name = 'sparql/graph-list'
    def get_subjects(self, graph):
        return sorted(graph.subjects(NS.rdf.type, NS.sd.Graph))
    def get_additional_context(self, request):
        return {'store': self.store}
    def process_response(self, request, response):
        response['X-URI-Lookup'] = reverse('sparql-admin:view', args=[self.store_name]) + '?uri='
        response['X-SPARQL-Endpoint'] = reverse('sparql-admin:query', args=[self.store_name])
        return response

class GraphView(ContentNegotiatedView):
    graph_data_view = staticmethod(GraphDataView.as_view())
    graph_list_view = staticmethod(GraphListView.as_view())
    def get(self, request, store):
        if 'graph' in request.GET:
            return self.graph_data_view(request, store=store)
        else:
            return self.graph_list_view(request, store=store)
    post = delete = put = get

if 'humfrey.elasticsearch' in settings.INSTALLED_APPS:
    from humfrey.elasticsearch import views as elasticsearch_views

    class SearchView(StoreChooseMixin, elasticsearch_views.SearchView):
        pass

    class ElasticSearchPassThroughView(StoreChooseMixin, StoreView, misc_views.PassThroughView):
        permission_requirements = {'get': 'sparql.query_store',
                                   'post': 'sparql.query_store',
                                   'head': 'sparql.query_store'}
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
