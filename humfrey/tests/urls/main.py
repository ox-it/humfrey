from django.conf.urls.defaults import *
from django.conf import settings

from humfrey.desc import views as desc_views
from humfrey.images import views as images_views
from humfrey.sparql import views as sparql_views

#from humfrey.dataox.views import DatasetView, ExploreView, ExampleDetailView, ExampleResourceView, ExampleQueryView, ContactView, ForbiddenView, HelpView, ResizedImageView

urlpatterns = patterns('',
    (r'^id/.*$', desc_views.IdView.as_view(), {}, 'id'),

    (r'^doc.+$', desc_views.DocView.as_view(), {}, 'doc'),
    (r'^doc/$', desc_views.DocView.as_view(), {}, 'doc-generic'),
    (r'^desc/$', desc_views.DescView.as_view(), {}, 'desc'),

    (r'^sparql/$', sparql_views.SparqlView.as_view(), {}, 'sparql'),

    (r'^pingback/', include('humfrey.pingback.urls')),

    (r'^external-image/$', images_views.ResizedImageView.as_view(), {}, 'resized-image'),
)

