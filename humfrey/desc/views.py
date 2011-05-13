from urlparse import urlparse
import urllib, urllib2, rdflib, simplejson, hashlib, pickle, base64

from types import GeneratorType
from lxml import etree
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.cache import cache

from ..utils.views import BaseView, renderer
from ..utils.http import HttpResponseSeeOther, HttpResponseTemporaryRedirect, MediaType
from ..utils import sparql
from ..utils.resource import Resource, get_describe_query
from ..utils.namespaces import NS
from ..utils.cache import cached_view

from .forms import SparqlQueryForm

class EndpointView(BaseView):
    endpoint = sparql.Endpoint(settings.ENDPOINT_QUERY)

    def get_types(self, uri):
        key_name = 'types:%s' % hashlib.sha1(uri.encode('utf8')).hexdigest()
        types = cache.get(key_name)
        if types:
            types = pickle.loads(base64.b64decode(types))
        else:
            types = set(rdflib.URIRef(r.type) for r in self.endpoint.query('SELECT ?type WHERE { GRAPH ?g { %s a ?type } }' % uri.n3()))
            cache.set(key_name, base64.b64encode(pickle.dumps(types)), 1800)
        return types

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

    @renderer(format='kml', mimetypes=('application/vnd.google-earth.kml+xml',), name='KML')
    def render_kml(self, request, context, template_name):
        if not isinstance(context.get('graph'), rdflib.ConjunctiveGraph):
            raise NotImplementedError
        graph = context['graph']
        subjects = set()
        for s in set(graph.subjects()):
            subject = Resource(s, graph, self.endpoint)
            if subject.geo_lat and subject.geo_long and isinstance(subject, rdflib.URIRef):
                subjects.add(subject)
        context['subjects'] = subjects
        context['hostname'] = request.META['HTTP_HOST']

        return render_to_response('render.kml',
                                  context, context_instance=RequestContext(request),
                                  mimetype='application/vnd.google-earth.kml+xmll')


class SRXView(BaseView):
    def _spool_srx_boolean(self, result):
        yield '<?xml version="1.0"?>\n'
        yield '<sparql xmlns="http://www.w3.org/2005/sparql-results#">\n'
        yield '  <head/>\n'
        yield '  <boolean>%s</boolean>\n' % ('true' if result else 'false')
        yield '</sparql>\n'

    def _spool_srx_resultset(self, results):
        yield '<?xml version="1.0"?>\n'
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

    def _spool_srj_boolean(self, result):
        yield '{\n'
        yield '  "head": {},\n'
        yield '  "boolean": %s\n' % ('true' if result else 'false')
        yield '}\n'

    def _spool_srj_resultset(self, results):
        dumps = simplejson.dumps
        yield '{\n'
        yield '  "head": {\n'
        yield '    "vars": [ %s ]\n' % ', '.join(dumps(v) for v in results.fields)
        yield '  },\n'
        yield '  "results": [\n'
        for i, result in enumerate(results):
            yield '    {' if i == 0 else ',\n    {'
            for j, (name, value) in enumerate(result._asdict().iteritems()):
                yield ',\n' if j > 0 else '\n'
                yield '      %s: { "type": ' % dumps(name.encode('utf8'))
                if isinstance(value, rdflib.URIRef):
                    yield dumps('uri')
                elif isinstance(value, rdflib.BNode):
                    yield dumps('bnode')
                elif value.datatype:
                    yield '%s, "datatype": %s' % (dumps('typed-literal'), dumps(value.datatype.encode('utf8')))
                elif value.language:
                    yield '%s, "xml:lang": %s' % (dumps('literal'), dumps(value.language.encode('utf8')))
                else:
                    yield dumps('literal')
                yield ', "value": %s' % dumps(value.encode('utf8'))
            yield '\n    }'
        yield '\n  ]\n'
        yield '}\n'

    def _spool_csv_boolean(self, result):
        yield '%s\n' % ('true' if result else 'false')

    def _spool_csv_resultset(self, results):
        for result in results:
            yield ",".join(quote(v) for v in result)
            yield '\n'

    def render_resultset(self, request, context, spool_boolean, spool_resultset, mimetype):
        if isinstance(context.get('result'), bool):
            spool = spool_boolean(context['result'])
        elif isinstance(context.get('results'), list):
            spool = spool_resultset(context['results'])
        else:
            raise NotImplementedError
        return HttpResponse(spool, mimetype=mimetype)

    @renderer(format='srx', mimetypes=('application/sparql-results+xml',), name='SPARQL Results XML')
    def render_srx(self, request, context, template_name):
        return self.render_resultset(request, context,
                                     self._spool_srx_boolean,
                                     self._spool_srx_resultset,
                                     'application/sparql-results+xml')
        
    @renderer(format='srj', mimetypes=('application/sparql-results+json',), name='SPARQL Results JSON')
    def render_srj(self, request, context, template_name):
        return self.render_resultset(request, context,
                                     self._spool_srj_boolean,
                                     self._spool_srj_resultset,
                                     'application/sparql-results+json')

    @renderer(format='csv', mimetypes=('text/csv',), name='CSV')
    def render_csv(self, request, context, template_name):
        return self.render_resultset(request, context,
                                     self._spool_csv_boolean,
                                     self._spool_csv_resultset,
                                     'text/csv;charset=UTF-8')

class IndexView(BaseView):
    @cached_view
    def handle_GET(self, request, context):
        return self.render(request, context, 'index')

class IdView(EndpointView):
    def initial_context(self, request):
        uri = rdflib.URIRef(request.build_absolute_uri())
        if not self.get_types(uri):
            raise Http404
        return {
           'uri': uri,
           'description_url': DocView().get_description_url(request, uri),
        }

    @cached_view
    def handle_GET(self, request, context):
        return HttpResponseSeeOther(context['description_url'])

class DescView(EndpointView):
    """
    Will redirect to DocView if described by endpoint, otherwise to the URI given.

    Allows us to be lazy when determining whether to go on- or off-site.
    """
    def handle_GET(self, request, context):
        uri = rdflib.URIRef(request.GET.get('uri', ''))
        try:
            url = urlparse(uri)
        except Exception:
            raise
            raise Http404
        if self.get_types(uri):
            return HttpResponsePermanentRedirect(DocView().get_description_url(request, uri))
        elif url.scheme in ('http', 'https') and url.netloc and url.path.startswith('/'):
            return HttpResponseTemporaryRedirect(unicode(uri))
        else:
            raise Http404

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
            # FIXME!
            description_url = 'http://%s/doc/?%s' % ('data.ox.ac.uk', urllib.urlencode(params))

        return description_url

    def initial_context(self, request):
        if request.path == '/doc/':
            if 'uri' not in request.GET:
                raise Http404
            uri = request.GET['uri']
            format = request.GET.get('format')
            with_fragments = False
            show_follow_link, no_index = True, True
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
            show_follow_link, no_index = False, False
        uri = rdflib.URIRef(uri)

        types = self.get_types(uri)
        if not types:
            raise Http404

        graph = self.endpoint.query(get_describe_query(uri, types))
        subject = Resource(uri, graph, self.endpoint)

        if False and with_fragments:
            graph += self.endpoint.query('DESCRIBE ?s WHERE { ?s ?p ?o . FILTER (regex(?s, "^%s#")) }' % uri)

        doc_uri = rdflib.URIRef(self.get_description_url(request, uri))
        
        licenses, datasets = set(), set()
        for graph_name in graph.subjects(NS['ov'].describes):
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
        
        
        formats = sorted([(r, self.get_description_url(request, uri, r.format)) for r in self.FORMATS.values()], key=lambda x:x[0].name)
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
            'licenses': [Resource(uri, graph, self.endpoint) for uri in licenses],
            'datasets': [Resource(uri, graph, self.endpoint) for uri in datasets],
            'formats': formats,
            'show_follow_link': show_follow_link,
            'no_index': no_index,
        }

    @cached_view
    def handle_GET(self, request, context):
        if context['format']:
            try:
                return self.render_to_format(request, context, context['subject'].template_name, context['format'])
            except KeyError:
                raise Http404
        else:
            return self.render(request, context, context['subject'].template_name)


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

