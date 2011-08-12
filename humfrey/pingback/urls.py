from django.conf.urls.defaults import *

from views import XMLRPCPingbackView, RESTfulPingbackView, ModerationView

urlpatterns = patterns('',
    (r'^xmlrpc/$', XMLRPCPingbackView.as_view(), {}, 'pingback-xmlrpc'),
    (r'^rest/$', RESTfulPingbackView.as_view(), {}, 'pingback-rest'),
    (r'^moderation/$', ModerationView.as_view(), {}, 'pingback-moderation'),
)
