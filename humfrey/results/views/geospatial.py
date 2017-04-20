import rdflib

from django.shortcuts import render
from django.template import RequestContext

from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView

from humfrey.linkeddata.resource import Resource

class KMLView(ContentNegotiatedView):
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

        return render(request, 'results/graph.kml', context,
                      content_type='application/vnd.google-earth.kml+xml')
