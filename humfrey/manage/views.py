from django.contrib.auth import views as auth_views
from django_conneg.views import HTMLView
from humfrey.utils.views import AuthenticatedView, SecureView

class IndexView(HTMLView, AuthenticatedView):
    def get(self, request):
        context = {}
        return self.render(request, context, 'admin/index')
    
class LoginView(SecureView):
    def get(self, request, *args, **kwargs):
        return auth_views.login(request, *args, **kwargs)
    post = get

class LogoutView(SecureView):
    def get(self, request, *args, **kwargs):
        return auth_views.logout(request, *args, **kwargs)
    post = get
