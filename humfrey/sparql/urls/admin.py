from django.conf.urls import url, patterns

from humfrey.sparql.views import admin as admin_views

urlpatterns = patterns('',
    url(r'^$', admin_views.IndexView.as_view(), name='index'),
    url(r'^(?P<store>[a-z\-]+)/query/$', admin_views.QueryView.as_view(default_timeout=10,
                                    maximum_timeout=10), name='query'),
    url(r'^(?P<store>[a-z\-]+)/data/$', admin_views.GraphView.as_view(), name='data'),
    url(r'^(?P<store>[a-z\-]+)/view/$', admin_views.DocView.as_view(), name='view'),
)

if admin_views.SearchView:
    urlpatterns += patterns('',
        url(r'^(?P<store>[a-z\-]+)/search/$', admin_views.SearchView.as_view(), name='search'),
        url(r'^(?P<store>[a-z\-]+)/elasticsearch/(?:(?P<index>[a-z\-]+)/)?$', admin_views.ElasticSearchPassThroughView.as_view(), name='elasticsearch'),
    )
