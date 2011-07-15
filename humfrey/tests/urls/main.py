from django.conf.urls.defaults import *
from django.conf import settings

from humfrey.desc import views as desc_views
from humfrey.images import views as images_views

#from humfrey.dataox.views import DatasetView, ExploreView, ExampleDetailView, ExampleResourceView, ExampleQueryView, ContactView, ForbiddenView, HelpView, ResizedImageView

urlpatterns = patterns('',
    (r'^id/.*$', desc_views.IdView(), {}, 'id'),

    (r'^doc.+$', desc_views.DocView(), {}, 'doc'),
    (r'^doc/$', desc_views.DocView(), {}, 'doc-generic'),
    (r'^desc/$', desc_views.DescView(), {}, 'desc'),

    (r'^sparql/$', desc_views.SparqlView(), {}, 'sparql'),

    (r'^pingback/', include('humfrey.pingback.urls')),

    (r'^external-image/$', images_views.ResizedImageView(), {}, 'resized-image'),
)

