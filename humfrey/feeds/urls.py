from django.conf.urls import url, patterns

from . import views

urlpatterns = patterns('', 
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^(?P<slug>[a-z\d-]+)/$', views.FeedRenderView.as_view(), name='feed-render'),
    url(r'^(?P<slug>[a-z\d-]+)/config/$', views.FeedConfigView.as_view(), name='feed-config'),
)
