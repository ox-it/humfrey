from django.conf.urls import *

from humfrey.sparql import views

urlpatterns = patterns('',
    (r'^$', views.ProtectedQueryView.as_view(default_timeout=10,
                                             maximum_timeout=10), {}, 'endpoint'),
)
