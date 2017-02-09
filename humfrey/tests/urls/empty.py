from django.conf.urls import *
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

urlpatterns = [
    url(r'^login/$', 'django.contrib.auth.views.login'),
    url(r'^logout/$', 'django.contrib.auth.views.logout'),
    url(r'^login_required/$', login_required(lambda request: HttpResponse())),
]
