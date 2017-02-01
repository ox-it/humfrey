from django.conf.urls import *

from .views import IdView, DocView

urlpatterns = patterns('',
    (r'^id/.*$', IdView(), {}, 'id'),
    (r'^doc/.*$', DocView(), {}, 'doc'),
    (r'^all.*$', DocView(), {}, 'all'),
)
