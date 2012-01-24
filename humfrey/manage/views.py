from django_conneg.views import HTMLView

class IndexView(HTMLView):
    def get(self, request):
        context = {}
        return self.render(request, context, 'manage/index')
