from django.conf.urls.defaults import *

from . import views

urlpatterns = patterns('',
    (r'^$', views.IndexView.as_view(), {}, 'index'),
    (r'^(?P<id>[a-z\d-]+)/$', views.ListView.as_view(), {}, 'list'),
)
