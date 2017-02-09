from django.conf import settings
from django.conf.urls import url, include

from humfrey.desc import views as desc_views
from humfrey.thumbnail import views as thumbnail_views
from humfrey.sparql import views as sparql_views
from humfrey.misc import views as misc_views

urlpatterns = [
    url(r'^id/.*$', desc_views.IdView.as_view(), name='id'),

    url(r'^doc.+$', desc_views.DocView.as_view(), name='doc'),
    url(r'^doc/$', desc_views.DocView.as_view(), name='doc-generic'),
    url(r'^desc/$', desc_views.DescView.as_view(), name='desc'),

    url(r'^sparql/$', sparql_views.QueryView.as_view(), name='sparql'),

    url(r'^thumbnail/$', thumbnail_views.ThumbnailView.as_view(), name='thumbnail'),
]

if 'humfrey.pingback' in settings.INSTALLED_APPS:
    urlpatterns.append(url(r'^pingback/', include('humfrey.pingback.urls', 'pingback')))


handler404 = misc_views.SimpleView.as_view(template_name='404', context={'status_code':404})
handler500 = misc_views.SimpleView.as_view(template_name='500', context={'status_code':500})
