from django.conf.urls.defaults import url, patterns

from humfrey.sparql import views

urlpatterns = patterns('',
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^(?P<store>[a-z\-]+)/query/$', views.QueryView.as_view(default_timeout=10,
                                    maximum_timeout=10), name='query'),
)
