from django.conf.urls.defaults import *

from views import IdView, DocView

urlpatterns = patterns('',
    (r'^id/.*$', IdView(), {}, 'id'),
    (r'^doc/.*$', DocView(), {}, 'doc'),
    (r'^all.*$', DocView(), {}, 'all'),
)
