from django.conf.urls import *
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

urlpatterns = patterns('',
    (r'^login/$', 'django.contrib.auth.views.login'),
    (r'^logout/$', 'django.contrib.auth.views.logout'),
    (r'^login_required/$', login_required(lambda request: HttpResponse())),
    (r'^', include('object_permissions.urls')),
)

