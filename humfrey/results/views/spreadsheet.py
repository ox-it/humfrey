from django.shortcuts import render_to_response
from django.template import RequestContext
from humfrey.utils.views import EndpointView
from django_conneg.decorators import renderer

class SpreadsheetView(EndpointView):
    @renderer(format='xls', mimetypes=('application/vnd.ms-excel',), name='Excel spreadsheet')
    def render_xls(self, request, context, template_name):
        return render_to_response('results/resultset.xls',
                                  context, context_instance=RequestContext(request),
                                  mimetype='application/vnd.ms-excel')
