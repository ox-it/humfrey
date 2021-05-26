from django.conf.urls import url

from humfrey.sparql import views

app_name = 'sparql'

urlpatterns = [
    url(r'^$', views.ProtectedQueryView.as_view(default_timeout=10,
                                                maximum_timeout=10), name='endpoint'),
]
