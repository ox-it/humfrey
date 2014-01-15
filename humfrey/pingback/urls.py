from django.conf.urls import patterns, url

from humfrey.pingback import views

urlpatterns = patterns('',
    url(r'^xmlrpc/$', views.XMLRPCPingbackView.as_view(), name='xmlrpc'),
    url(r'^rest/$', views.RESTfulPingbackView.as_view(), name='rest'),
)
