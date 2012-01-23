from django.conf.urls.defaults import *

from humfrey.update import views

urlpatterns = patterns('',
    url(r'^$', views.IndexView.as_view(), {}, 'index'),
    url(r'^create/$', views.DefinitionDetailView.as_view(), name='definition-create'),
    url(r'^files/$', views.FileListView.as_view(), name='file-list'),
    url(r'^files/(?P<name>[^/]+)$', views.FileDetailView.as_view(), name='file-detail'),
    url(r'^files/(?P<name>.+)/permissions/$', views.FileDetailPermissionsView.as_view(), name='file-permissions'),
    url(r'^(?P<slug>[a-z\d\-]+)/$', views.DefinitionDetailView.as_view(), name='definition-detail'),
    url(r'^(?P<slug>[a-z\d\-]+)/log/$', views.UpdateLogListView.as_view(), name='log-list'),
    url(r'^(?P<slug>[a-z\d\-]+)/log/(?P<id>\d+)/$', views.UpdateLogDetailView.as_view(), name='log-detail'),
)
