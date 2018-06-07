import subprocess

import rdflib

from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.template import RequestContext, loader
from django.template.defaultfilters import slugify
from django.shortcuts import render

from django_conneg.http import HttpBadRequest
from django_conneg.decorators import renderer

from humfrey.results.views.standard import RDFView
from humfrey.sparql.views.core import StoreView
from humfrey.linkeddata.views import MappingView
from humfrey.linkeddata.resource import Resource
from humfrey.utils.namespaces import expand, NS

class GraphVizView(RDFView, StoreView, MappingView):
    query = """
      CONSTRUCT {{
        {page_uri} foaf:topic ?entity .
        ?entity a ?type ;
          rdfs:label ?title .
        {relationPattern}
      }} WHERE {{
        {{
          SELECT DISTINCT ?entity WHERE {{
            {selector}
          }} LIMIT 10000
        }} 
        ?entity a ?type .
        OPTIONAL {{
          VALUES ?relation {{ {relations} }}
          {relationPattern}
        }} .
        OPTIONAL {{ ?entity rdfs:label|dc:title|skos:prefLabel|foaf:name ?title }} .
        NOT EXISTS {{
          VALUES ?excludedType {{ {excludedTypes} }}
          ?entity a ?excludedType
        }}
      }}
    """
    
    type_selector = """
            ?orgType rdfs:subClassOf* {baseType}
            GRAPH {graph} {{ ?entity a ?orgType }}
    """
    
    tree_selector = """
            {subject} {relationAlternation}{{0,{depth}}} {object}
    """
    
    def get(self, request, root=None, base_type=None, graph=None, relations=None, template='graphviz/graphviz', depth=4, max_depth=5, excluded_types=None, properties=None, inverted=None, minimal=None):
        make_uriref = lambda uri: expand(uri) if uri else None
        root = make_uriref(root or request.GET.get('root'))
        base_type = make_uriref(base_type or request.GET.get('base_type'))
        graph = make_uriref(graph or request.GET.get('graph'))

        relations = relations or [expand(relation) for relation in request.GET.getlist('relation')]
        inverted = inverted if (inverted is not None) else request.GET.get('inverted') == 'true'
        minimal = minimal if (minimal is not None) else request.GET.get('minimal') == 'true'

        if not relations:
            raise Http404

        if inverted:
            relation_pattern = '?entity ?relation ?parent'
        else:
            relation_pattern = '?parent ?relation ?entity'

        if root and base_type:
            raise HttpBadRequest
        elif root:
            if not self.get_types(root):
                raise Http404

            if inverted:
                subj, obj = '?entity', root.n3()
            else:
                subj, obj = root.n3(), '?entity'

            try:
                depth = min(int(request.GET.get('depth', depth)), max_depth)
            except (TypeError, ValueError):
                return HttpResponseBadRequest()
            selector = self.tree_selector.format(subject=subj,
                                                 object=obj,
                                                 depth=depth,
                                                 relationAlternation='|'.join(r.n3() for r in relations))
        elif base_type:
            selector = self.type_selector.format(graph=graph.n3() if graph else '?graph',
                                                 baseType=base_type.n3())

        excluded_types = excluded_types or [expand(t) for t in request.GET.getlist('exclude_type')]
        properties = properties or [expand(p) for p in request.GET.getlist('property')]

        page_uri = rdflib.URIRef(request.build_absolute_uri())

        query = self.query.format(selector=selector,
                                  relations=' '.join(r.n3() for r in relations),
                                  excludedTypes=' '.join(t.n3() for t in excluded_types),
                                  relationPattern=relation_pattern,
                                  page_uri=page_uri.n3(),
                                  propertyPatterns='\n        '.join('OPTIONAL { ?entity %s ?p%s } .' % (p.n3(), i) for i, p in enumerate(properties)),
                                  propertyTriples=''.join(';\n          %s ?p%s' % (p.n3(), i) for i, p in enumerate(properties))
                               )
        graph = self.endpoint.query(query)

        subjects = [Resource(s, graph, self.endpoint) for s in set(graph.objects(page_uri, NS['foaf'].topic))]
        subjects.sort(key=lambda s: s.label)

        subject = Resource(root, graph, self.endpoint) if root else None

        context = {
            'graph': graph,
            'queries': [graph.query],
            'subjects': subjects,
            'subject': subject,
            'inverted': inverted,
            'relations': relations,
            'minimal': minimal,
            'filename_base': slugify(subject.label if subject else 'graphviz')[:32]
        }

        for subject in subjects:
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
            plain_gv = template.render(context)
            dot = subprocess.Popen(['dot', '-K'+layout, '-T'+dot_output], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            dot_stdout, _ = dot.communicate(input=plain_gv.encode('utf-8'))
            response = HttpResponse(dot_stdout, content_type=output['mimetypes'][0])
            response['Content-Disposition'] = 'inline; filename="{0}.{1}"'.format(context['filename_base'],
                                                                                  output['format'])
            return response

        dot_output = output.pop('dot_output')
        dot_renderer.__name__ = 'render_%s' % output['format']
        return renderer(**output)(dot_renderer)

    for output in _DOT_OUTPUTS:
        locals()['render_%s' % output['format']] = _get_dot_renderer(output)
    del _get_dot_renderer, output

    @renderer(format="graphml", mimetypes=('application/x-graphml+xml',), name="GraphML")
    def render_graphml(self, request, context, template_name):
        response = render(request, template_name + '.graphml', context,
                          content_type='application/x-graphml+xml')
        response['Content-Disposition'] = 'attachment; filename="{0}.graphml"'.format(context['filename_base'])
        return response
