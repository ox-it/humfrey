from urlparse import urlparse
import urllib, urllib2, rdflib, simplejson

from lxml import etree
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import Http404, HttpResponse

from ..utils.views import BaseView, renderer
from ..utils.http import HttpResponseSeeOther, MediaType
from ..utils import sparql
from ..utils.resource import Resource
from ..utils.namespaces import NS
from ..utils.cache import cached_view

from .forms import SparqlQueryForm

class EndpointView(BaseView):
    endpoint = sparql.Endpoint(settings.ENDPOINT_URL)

class RDFView(BaseView):
    def render_generic_rdf(self, graph, method, mimetype):
        return HttpResponse(graph.serialize(format=method), mimetype=mimetype)

    RDF_SERIALIZATIONS = (
        ('rdf', 'application/rdf+xml', 'pretty-xml', 'RDF/XML'),
        ('nt', 'text/plain', 'nt', 'N-Triples'),
        ('ttl', 'text/turtle', 'turtle', 'Turtle'),
        ('n3', 'text/n3', 'n3', 'Notation3'),
    )

    for format, mimetype, method, name in RDF_SERIALIZATIONS:
        def f(format, mimetype, method, name):
            @renderer(format=format, mimetypes=(mimetype,), name=name)
            def render(self, request, context, template_name):
                if not isinstance(context.get('graph'), rdflib.ConjunctiveGraph):
                    raise NotImplementedError
                return self.render_generic_rdf(context['graph'], method, mimetype)
            render.__name__ = 'render_%s' % format
            return render
        locals()['render_%s' % format] = f(format, mimetype, method, name)
    del f, format, mimetype, method, name

class SRXView(BaseView):
    @renderer(format='srx', mimetypes=('application/sparql-results+xml',), name='SPARQL Results XML')
    def render_srx(self, request, context, template_name):
        if not isinstance(context.get('results'), list):
            raise NotImplementedError
        def spool(results):
            yield '<?xml version="1.0">\n'
            yield '<sparql xmlns="http://www.w3.org/2005/sparql-results#">\n'
            yield '  <head>\n'
            for binding in results.fields:
                yield '    <variable name="%s"/>\n' % escape(binding)
            yield '  </head>\n'
            yield '  <results>\n'
            for result in results:
                yield '    <result>\n'
                for field in result._fields:
                    yield '      <binding name="%s">\n' % escape(field)
                    yield ' '*8
                    value = getattr(result, field)
                    if isinstance(value, rdflib.URIRef):
                        yield '<uri>%s</uri>' % escape(value).encode('utf-8')
                    elif isinstance(value, rdflib.BNode):
                        yield '<bnode>%s</bnode>' % escape(value).encode('utf-8')
                    elif isinstance(value, rdflib.Literal):
                        yield '<literal'
                        if value.datatype:
                            yield ' datatype="%s"' % escape(value.datatype).encode('utf-8')
                        if value.language:
                            yield ' xml:lang="%s"' % escape(value.language).encode('utf-8')
                        yield '>%s</literal>' % escape(value).encode('utf-8')
                    yield '\n      </binding>\n'
                yield '    </result>\n'
            yield '  </results>\n'
            yield '</sparql>\n'
 
        return HttpResponse(spool(context['results']), mimetype='application/sparql-results+xml')
        
    @renderer(format='csv', mimetypes=('text/csv',), name='CSV')
    def render_csv(self, request, context, template_name):
        if not isinstance(context.get('results'), list):
            raise NotImplementedError
        def quote(value):
            value = value.replace(r'"', r'\"')
            if any(c in ' \n\t' for c in value):
                value = value.replace('\n', r'\n')
                value = '"%s"' % value
            return value
        def spool(results):
            for result in results:
                yield ",".join(quote(v) for v in result)
                yield '\n'
        return HttpResponse(spool(context['results']), mimetype='text/csv')
    
    @renderer(format='srj', mimetypes=('application/sparql-results+json',), name='SPARQL Results JSON')
    def render_srj(self, request, context, template_name):
        if not isinstance(context.get('results'), list):
            raise NotImplementedError
        results = context['results']
        bindings = []
        data = {
            'head': {'vars': results.fields},
            'results': {'bindings': bindings},
        }
        for result in results:
            binding = {}
#            raise Exception(unicode)
            for name, value in result._asdict().iteritems():
                if isinstance(value, rdflib.URIRef):
                    #raise Exception(type(value))
                    binding[name] = {'type': 'uri', 'value': unicode(value)}
                elif isinstance(value, rdflib.BNode):
                    binding[name] = {'type': 'bnode', 'value': unicode(value)}
                elif isinstance(value, rdflib.Literal):
                    binding[name] = {'type': 'literal', 'value': unicode(value)}
                    if value.datatype:
                        binding[name]['datatype'] = unicode(value.datatype)
                    elif value.language:
                        binding[name]['xml:lang'] = unicode(value.language)
            bindings.append(binding)
        return HttpResponse(simplejson.dumps(data), mimetype='application/sparql-results+json')
        

class IndexView(BaseView):
    @cached_view
    def handle_GET(self, request, context):
        return self.render(request, context, 'index')

class IdView(EndpointView):
    def initial_context(self, request):
        uri = rdflib.URIRef(request.build_absolute_uri())
        contained = self.endpoint.query('ASK WHERE { GRAPH ?g { %s ?p ?o } }' % uri.n3())
        if not contained:
            raise Http404
        return {
           'uri': uri,
           'description_url': DocView().get_description_url(request, uri),
        }

    @cached_view
    def handle_GET(self, request, context):
        return HttpResponseSeeOther(context['description_url'])

class DocView(EndpointView, RDFView):
    def get_description_url(self, request, uri, format=None):
        uri = urlparse(uri)
        if request and not format:
            accepts = self.parse_accept_header(request.META['HTTP_ACCEPT'])
            renderers = MediaType.resolve(accepts, self.FORMATS_BY_MIMETYPE)
            if renderers:
                format = renderers[0].format
        
        if uri.netloc in settings.SERVED_DOMAINS and uri.scheme == 'http' and uri.path.startswith('/id/') and not uri.query and not uri.params:
            description_url = '%s://%s/doc/%s' % (uri.scheme, uri.netloc, uri.path[4:])
            if format:
                description_url += '.' + format
        else:
            params = {'uri': uri.geturl()}
            if format:
                params['format'] = format
            description_url = '/doc/?' + urllib.urlencode(params)

        return description_url

    def initial_context(self, request):
        if request.path == '/doc/':
            if 'uri' not in request.GET:
                raise Http404
            uri = request.GET['uri']
            format = request.GET.get('format')
            with_fragments = False
        else:
            uri = urlparse(request.build_absolute_uri())
            if request.path.startswith('/doc/'):
                uri = '%s://%s/id/%s' % (uri.scheme, uri.netloc, uri.path[5:])
            else:
                uri = request.build_absolute_uri()
            for format in self.FORMATS:
                if uri.endswith('.' + format):
                    uri = uri[:-(1+len(format))]
                    request.path = request.path[:-(1+len(format))]
                    break
            else:
                format = None
            with_fragments = True
        uri = rdflib.URIRef(uri)

        graph = self.endpoint.describe(uri)
        subject = Resource(uri, graph, self.endpoint)

        if False and with_fragments:
            graph += self.endpoint.query('DESCRIBE ?s WHERE { ?s ?p ?o . FILTER (regex(?s, "^%s#")) }' % uri)

        doc_uri = rdflib.URIRef(self.get_description_url(None, uri))
        
        licenses, datasets = set(), set()
        for graph_name in graph.subjects(NS['ov'].describes, uri):
            graph.add((doc_uri, NS['dcterms'].source, graph_name))
            licenses.update(graph.objects(graph_name, NS['dcterms'].license))
            datasets.update(graph.objects(graph_name, NS['void'].inDataset))
            
        if len(licenses) == 1:
            for license in licenses:
                graph.add((doc_uri, NS['dcterms'].license, license))

        if not graph:
            raise Http404
            
        graph.add((doc_uri, NS['foaf'].primaryTopic, uri))
        graph.add((doc_uri, NS['rdf'].type, NS['foaf'].Document))
        graph.add((doc_uri, NS['dcterms']['title'], rdflib.Literal('Description of %s' % subject.label)))
        
        
        formats = sorted([(r, self.get_description_url(None, uri, r.format)) for r in self.FORMATS.values()], key=lambda x:x[0].name)
        for renderer, url in formats:
            url = rdflib.URIRef(url)
            map(graph.add, [
                (doc_uri, NS['dcterms'].hasFormat, url),
                (url, NS['dcterms']['title'], rdflib.Literal('%s description of %s' % (renderer.name, subject.label))),
            ] + [(url, NS['dc']['format'], rdflib.Literal(mimetype)) for mimetype in renderer.mimetypes]
            )
             
            

        return {
            'uri': uri,
            'format': format,
            'graph': graph,
            'subject': subject,
            'licenses': (Resource(uri, graph, self.endpoint) for uri in licenses),
            'datasets': (Resource(uri, graph, self.endpoint) for uri in datasets),
            'formats': formats,
        }

    @cached_view
    def handle_GET(self, request, context):
        print context['formats']
        if context['format']:
            try:
                return self.render_to_format(request, context, 'doc', context['format'])
            except KeyError:
                raise Http404
        else:
            return self.render(request, context, 'doc')

class SparqlView(EndpointView, RDFView, SRXView):    
    def perform_query(self, query, common_prefixes):
        return self.endpoint.query(query, timeout=5, common_prefixes=common_prefixes)
    
    def initial_context(self, request):
        query = request.REQUEST.get('query')
        data = dict(request.REQUEST.items())
        if not 'format' in data:
            data['format'] = 'html'
        form = SparqlQueryForm(data if query else None, formats=self.FORMATS)
        context = {
            'namespaces': NS,
            'query': query,
            'form': form,
        }
        
        if not form.is_valid():
            return context

        try:        
            results = self.perform_query(query, form.cleaned_data['common_prefixes'])
        except urllib2.HTTPError, e:
            context['error'] = etree.parse(e).find('.//pre').text
            context['status_code'] = e.code
            return context
        
        if isinstance(results, list):
            context['results'] = results
        elif isinstance(results, bool):
            context['result'] = results
        elif isinstance(results, rdflib.ConjunctiveGraph):
            context['graph'] = results
            context['subjects'] = results.subjects()
        
        return context
    
    def handle_GET(self, request, context):
        return self.render(request, context, 'sparql')
    handle_POST = handle_GET
        
#class GraphView(BaseView):
#    def handle_GET(self, request, context):
#        req = urllib2.Request(settings.GRAPH_URL + '?' + urllib.urlencode({'graph': request.build_absolute_uri()}))
#        for header in request.META:
#            if header.startswith('
#            req.headers[header] = request.headers[header]
#            
#        try:
#            resp = urllib2.urlopen(req)
#        except urllib2.HTTPError, e:
#            resp = e
#        response = HttpResponse(response, status_code=e.code)
#        
#        return response

