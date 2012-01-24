from django.conf.urls.defaults import patterns, url

from humfrey.pingback import views

urlpatterns = patterns('',
    url(r'^moderation/$', views.ModerationView.as_view(), name='moderation'),
)
