from django.conf.urls.defaults import *

from humfrey.update import views

urlpatterns = patterns('',
    (r'^$', views.IndexView.as_view(), {}, 'update-index'),
    (r'^trigger/$', views.TriggerView.as_view(), {}, 'update-trigger'),
    (r'^trigger/(?P<id>[a-z-\d]+)/$', views.TriggerView.as_view()),
)
