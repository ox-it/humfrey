from django.conf.urls.defaults import *

from humfrey.sparql import views

urlpatterns = patterns('',
    (r'^$', views.QueryView.as_view(default_timeout=10,
                                    maximum_timeout=10), {}, 'endpoint'),
)
