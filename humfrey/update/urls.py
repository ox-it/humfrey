from django.conf.urls.defaults import *

from humfrey.update import views

urlpatterns = patterns('',
    (r'^$', views.IndexView.as_view(), {}, 'index'),
    (r'^trigger/$', views.TriggerView.as_view(), {}, 'trigger'),
    (r'^trigger/(?P<id>[a-z-\d]+)/$', views.TriggerView.as_view()),
)
