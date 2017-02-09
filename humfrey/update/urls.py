from django.conf.urls import url

from humfrey.update import views

urlpatterns = [
    url(r'^$', views.IndexView.as_view(), {}, 'index'),
    url(r'^create/$', views.DefinitionDetailView.as_view(), name='definition-create'),
    url(r'^(?P<slug>[a-z\d\-]+)/$', views.DefinitionDetailView.as_view(), name='definition-detail'),
    url(r'^(?P<slug>[a-z\d\-]+)/log/$', views.UpdateLogListView.as_view(), name='log-list'),
    url(r'^(?P<slug>[a-z\d\-]+)/log/(?P<id>\d+)/$', views.UpdateLogDetailView.as_view(), name='log-detail'),
]
