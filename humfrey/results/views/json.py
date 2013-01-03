from __future__ import absolute_import

try:
    import simplejson as json
except ImportError:
    import json

from django.http import HttpResponse
import rdflib

from humfrey.linkeddata.resource import BaseResource
from humfrey.utils.namespaces import contract

from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView

# FIXME: This seems to get into unbounded recursion, so I'm disabling it for now.

class JSONRDFView(ContentNegotiatedView):
    def render_json_subject(self, graph, subject, seen=()):
        data, inv_data = {}, {}
        if isinstance(subject, rdflib.URIRef):
            data['_uri'] = unicode(subject)
        elif isinstance(subject, rdflib.BNode):
            data['_id'] = unicode(subject)
        if subject in seen:
            data['_nested'] = True
            return data
        seen += (subject,)

        for p in graph.predicates(subject):
            data[contract(p, '_')] = objects = []
            for o in graph.objects(subject, p):
                if isinstance(o, rdflib.Literal):
                    objects.append(unicode(o))
                else:
                    objects.append(self.render_json_subject(graph, o, seen))

        for p in graph.predicates(object=subject):
            objects = []
            for o in graph.subjects(p, subject):
                if len(seen) >= 2 and o == seen[-2]:
                    continue
                if isinstance(o, rdflib.Literal):
                    objects.append(unicode(o))
                else:
                    objects.append(self.render_json_subject(graph, o, seen))
            if objects:
                inv_data[contract(p)] = objects
        if inv_data:
            data['_inv'] = inv_data

        return data

    def render_json_test(self, request, context, template_name):
        return 'graph' in context and ('subject' in context or 'subjects' in context)

    def render_json_data(self, context):
        def coerce_subject(subject):
            if isinstance(subject, basestring):
                return rdflib.URIRef(subject)
            elif isinstance(subject, BaseResource):
                return subject._identifier
            elif isinstance(subject, (rdflib.URIRef, rdflib.BNode)):
                return subject
            else:
                raise AssertionError

        graph = context['graph']
        if 'subject' in context:
            return self.render_json_subject(graph, coerce_subject(context['subject']))
        else:
            return [self.render_json_subject(graph, coerce_subject(s)) for s in context['subjects']]

    #@renderer(format='json', mimetypes=('application/json',), name='JSON', test=render_json_test)
    def render_json(self, request, context, template_name):
        data = self.render_json_data(context)
        return HttpResponse(json.dumps(data, indent=2), mimetype="application/json")

    #@renderer(format='js', mimetypes=('application/javascript','text/javascript'), name='JavaScript (JSONP)', test=render_json_test)
    def render_js(self, request, context, template_name):
        callback = request.REQUEST.get('callback', 'callback')
        data = [callback, '(', self.render_json_data(context), ');']
        return HttpResponse(json.dumps(data, indent=2), mimetype="application/javascript")

