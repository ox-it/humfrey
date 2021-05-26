from django.conf.urls import url

from . import views

app_name = "feeds"

urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^(?P<slug>[a-z\d-]+)/$', views.FeedRenderView.as_view(), name='feed-render'),
    url(r'^(?P<slug>[a-z\d-]+)/config/$', views.FeedConfigView.as_view(), name='feed-config'),
]
