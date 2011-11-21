from django.conf.urls.defaults import *

from humfrey.update import views

urlpatterns = patterns('',
    url(r'^$', views.IndexView.as_view(), {}, 'index'),
    url(r'^create/$', views.DefinitionDetailView.as_view(), name='definition-create'),
    url(r'^(?P<slug>[a-z\d\-]+)/$', views.DefinitionDetailView.as_view(), name='definition-detail'),
)
