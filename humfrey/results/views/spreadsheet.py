from django.shortcuts import render
from django.template import RequestContext

from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView

class SpreadsheetView(ContentNegotiatedView):
    @renderer(format='xls', mimetypes=('application/vnd.ms-excel',), name='Excel spreadsheet')
    def render_xls(self, request, context, template_name):
        return render(request, 'results/resultset.xls', context,
                      content_type='application/vnd.ms-excel')
