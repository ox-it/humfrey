import rdflib

from django.shortcuts import render_to_response
from django.template import RequestContext

from django_conneg.decorators import renderer

from humfrey.utils.views import EndpointView
from humfrey.utils.resource import Resource

class KMLView(EndpointView):
    @renderer(format='kml', mimetypes=('application/vnd.google-earth.kml+xml',), name='KML')
    def render_kml(self, request, context, template_name):
        if not isinstance(context.get('graph'), rdflib.ConjunctiveGraph):
            return NotImplemented
        graph = context['graph']
        subjects = set()
        for subject in set(graph.subjects()):
            subject = Resource(subject, graph, self.endpoint)
            if subject.geo_lat and subject.geo_long and isinstance(subject, rdflib.URIRef):
                subjects.add(subject)
        context['subjects'] = subjects

        return render_to_response('results/graph.kml',
                                  context, context_instance=RequestContext(request),
                                  mimetype='application/vnd.google-earth.kml+xml')
