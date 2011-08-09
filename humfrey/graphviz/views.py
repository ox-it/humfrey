import subprocess

import rdflib

from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.template import RequestContext, loader
from django.template.defaultfilters import slugify
from django.shortcuts import render_to_response

from humfrey.linkeddata.views import RDFView
from humfrey.utils.resource import Resource
from humfrey.utils.views import renderer
from humfrey.utils.namespaces import expand, NS

class GraphVizView(RDFView):
    _QUERY = """
      CONSTRUCT {
        %(page_uri)s foaf:topic ?entity .
        ?entity a ?type %(propertyTriples)s .
          %(relationPattern)s .
      } WHERE {
        { SELECT DISTINCT ?entity WHERE { %(subject)s (%(relationAlternation)s){0,%(depth)d} %(object)s } } .
        ?entity a ?type .
        OPTIONAL { %(relationPattern)s } .
        %(propertyPatterns)s
        OPTIONAL { ?entity rdfs:label ?title } .
        FILTER (?relation in (%(relationList)s)) .
        %(excludeTypesFilter)s
      }
    """
    
    def handle_GET(self, request, context, root=None, relations=None, template='graphviz/graphviz', depth=4, max_depth=5, exclude_types=None, properties=None, inverted=None):
        root = expand(root or request.GET.get('root', ''))
        relations = relations or [expand(relation) for relation in request.GET.getlist('relation')]
        exclude_types = exclude_types or [expand(t) for t in request.GET.getlist('exclude_type')]
        properties = properties or [expand(p) for p in request.GET.getlist('property')]
        try:
            depth = min(int(request.GET.get('depth', depth)), max_depth)
        except (TypeError, ValueError):
            return HttpResponseBadRequest()
        
        inverted = inverted if (inverted is not None) else request.GET.get('inverted') == 'true'
        if inverted:
            subj, obj = '?entity', root.n3()
            relation_pattern = '?entity ?relation ?parent'
        else:
            subj, obj = root.n3(), '?entity'
            relation_pattern = '?parent ?relation ?entity'
        
        types = self.get_types(root)
        if not types or not relations:
            raise Http404
        
        page_uri = rdflib.URIRef(request.build_absolute_uri())
        
        query = self._QUERY % {'subject': subj,
                               'object': obj,
                               'depth': depth,
                               'relationList': ', '.join(r.n3() for r in relations),
                               'excludeTypesFilter': ('FILTER (?type not in (%s)) .' % ', '.join(t.n3() for t in exclude_types)) if exclude_types else '',
                               'relationAlternation': '|'.join(r.n3() for r in relations),
                               'relationPattern': relation_pattern,
                               'page_uri': page_uri.n3(),
                               'propertyPatterns': '\n        '.join('OPTIONAL { ?entity %s ?p%s } .' % (p.n3(), i) for i, p in enumerate(properties)),
                               'propertyTriples': ''.join(';\n          %s ?p%s' % (p.n3(), i) for i, p in enumerate(properties))
                               }
        graph = self.endpoint.query(query)
        
        context.update({
            'graph': graph,
            'queries': [graph.query],
            'subjects': [Resource(s, graph, self.endpoint) for s in set(graph.objects(page_uri, NS['foaf'].topic))],
            'subject': Resource(root, graph, self.endpoint),
            'inverted': inverted,
            'relations': relations,
        })
        
        for subject in context['subjects']:

            if not inverted:
                subject.children = set(Resource(s, graph, self.endpoint) for relation in relations for s in graph.objects(subject._identifier, relation))
            else:
                subject.children = set(Resource(s, graph, self.endpoint) for relation in relations for s in graph.subjects(relation, subject._identifier))
            for child in subject.children:
                if (page_uri, NS['foaf'].topic, child._identifier) in graph:
                    child.display = True
       
        return self.render(request, context, template)

    _DOT_LAYOUTS = "circo dot fdp neato nop nop1 nop2 osage patchwork sfdp twopi".split()
    _DOT_OUTPUTS = [
        dict(format='bmp', mimetypes=('image/x-bmp','image/x-ms-bmp'), name='BMP', dot_output='bmp'),
        dict(format='xdot', mimetypes=('text/vnd.graphviz',), name='xDOT', dot_output='xdot', priority=0.9),
        dict(format='gv', mimetypes=('text/vnd.graphviz',), name='DOT (GraphViz)', dot_output='gv'),
        dict(format='jpeg', mimetypes=('image/jpeg',), name='JPEG', dot_output='jpeg'),
        dict(format='png', mimetypes=('image/png',), name='PNG', dot_output='png'),
        dict(format='ps', mimetypes=('application/postscript',), name='PostScript', dot_output='ps'),
        dict(format='pdf', mimetypes=('application/pdf',), name='PDF', dot_output='pdf'),
        dict(format='svg', mimetypes=('image/svg+xml',), name='SVG', dot_output='svg'),
    ]
    
    def _get_dot_renderer(output):
        def dot_renderer(self, request, context, template_name):
            layout = request.GET.get('layout')
            if layout not in self._DOT_LAYOUTS:
                layout = 'fdp'
            template = loader.get_template(template_name + '.gv')
            plain_gv = template.render(RequestContext(request, context))
            dot = subprocess.Popen(['dot', '-K'+layout, '-T'+dot_output], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            dot_stdout, _ = dot.communicate(input=plain_gv.encode('utf-8'))
            response = HttpResponse(dot_stdout, mimetype=output['mimetypes'][0])
            response['Content-Disposition'] = 'inline; filename="%s.%s"' % (slugify(context['subject'].dcterms_title)[:32], output['format'])
            return response
        
        dot_output = output.pop('dot_output')
        dot_renderer.__name__ = 'render_%s' % output['format']
        return renderer(**output)(dot_renderer)
    
    for output in _DOT_OUTPUTS:
        locals()['render_%s' % output['format']] = _get_dot_renderer(output)
    del _get_dot_renderer, output


    @renderer(format="gv", mimetypes=('text/vnd.graphviz',), name="DOT (GraphViz)")
    def render_gv(self, request, context, template_name):
        layout = request.GET.get('layout')
        if layout not in self._DOT_LAYOUTS:
            layout = 'fdp'
        template = loader.get_template(template_name + '.gv')
        plain_gv = template.render(RequestContext(request, context))
        dot = subprocess.Popen(['dot', '-K'+layout, '-Txdot'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        dot_stdout, _ = dot.communicate(input=plain_gv.encode('utf-8'))
        response = HttpResponse(dot_stdout, mimetype='text/vnd.graphviz')
        response['Content-Disposition'] = 'attachment; filename="%s.gv"' % slugify(context['subject'].dcterms_title)[:32]
        return response

    @renderer(format="graphml", mimetypes=('application/x-graphml+xml',), name="GraphML")
    def render_graphml(self, request, context, template_name):
        response = render_to_response(template_name + '.graphml',
                                      context, context_instance=RequestContext(request),
                                      mimetype='application/x-graphml+xml')
        response['Content-Disposition'] = 'attachment; filename="%s.graphml"' % slugify(context['subject'].dcterms_title)[:32]
        return response