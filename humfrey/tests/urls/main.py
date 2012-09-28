from django.conf.urls.defaults import *

from humfrey.desc import views as desc_views
from humfrey.thumbnail import views as thumbnail_views
from humfrey.sparql import views as sparql_views
from humfrey.misc import views as misc_views

#from humfrey.dataox.views import DatasetView, ExploreView, ExampleDetailView, ExampleResourceView, ExampleQueryView, ContactView, ForbiddenView, HelpView, ResizedImageView

urlpatterns = patterns('',
    (r'^id/.*$', desc_views.IdView.as_view(), {}, 'id'),

    (r'^doc.+$', desc_views.DocView.as_view(), {}, 'doc'),
    (r'^doc/$', desc_views.DocView.as_view(), {}, 'doc-generic'),
    (r'^desc/$', desc_views.DescView.as_view(), {}, 'desc'),

    (r'^sparql/$', sparql_views.QueryView.as_view(), {}, 'sparql'),

    (r'^pingback/', include('humfrey.pingback.urls', 'pingback')),

    (r'^thumbnail/$', thumbnail_views.ThumbnailView.as_view(), {}, 'thumbnail'),

)


handler404 = misc_views.SimpleView.as_view(template_name='404', context={'status_code':404})
handler500 = misc_views.SimpleView.as_view(template_name='500', context={'status_code':500})
