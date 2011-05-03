from django.conf.urls.defaults import *

from views import XMLRPCPingbackView, RESTfulPingbackView, ModerationView

urlpatterns = patterns('',
    (r'^xmlrpc/$', XMLRPCPingbackView(), {}, 'pingback-xmlrpc'),
    (r'^rest/$', RESTfulPingbackView(), {}, 'pingback-rest'),
    (r'^moderation/$', ModerationView(), {}, 'pingback-moderation'),
)
