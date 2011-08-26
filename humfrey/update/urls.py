from django.conf.urls.defaults import *

from humfrey.update import views

urlpatterns = patterns('',
    (r'^$', views.IndexView.as_view(), {}, 'update-index'),
)
