from django.conf.urls.defaults import *

from . import views

urlpatterns = patterns('',
    (r'^$', views.SparqlView.as_view(), {}, 'endpoint'),
)
