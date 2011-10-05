from django.conf.urls.defaults import *

from views import XMLRPCPingbackView, RESTfulPingbackView, ModerationView

urlpatterns = patterns('',
    (r'^xmlrpc/$', XMLRPCPingbackView.as_view(), {}, 'xmlrpc'),
    (r'^rest/$', RESTfulPingbackView.as_view(), {}, 'rest'),
    (r'^moderation/$', ModerationView.as_view(), {}, 'moderation'),
)
