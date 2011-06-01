from urlparse import urlparse
import urllib, urllib2, rdflib, simplejson, hashlib, pickle, base64, redis, time

from types import GeneratorType
from lxml import etree
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.cache import cache

from humfrey.linkeddata.views import EndpointView, RDFView, ResultSetView

from humfrey.utils.views import BaseView
from humfrey.utils.http import HttpResponseSeeOther, HttpResponseTemporaryRedirect, MediaType
from humfrey.utils.resource import Resource, get_describe_query
from humfrey.utils.namespaces import NS
from humfrey.utils.cache import cached_view

from humfrey.desc.forms import SparqlQueryForm


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
    def get_description_url(self, request, uri, format=None, strip_format=False):
        uri = urlparse(uri)
        if request and not format:
            try:
                accepts = self.parse_accept_header(request.META['HTTP_ACCEPT'])
            except KeyError, e:
                # What are they playing at, not sending an Accept header?
                pass
            else:
                renderers = MediaType.resolve(accepts, self.FORMATS_BY_MIMETYPE)
                if renderers:
                    format = renderers[0].format
        
        if uri.netloc in settings.SERVED_DOMAINS and uri.scheme == 'http' and uri.path.startswith('/id/') and not uri.query and not uri.params:
            description_url = '%s://%s/doc/%s' % (uri.scheme, uri.netloc, uri.path[4:])
            if format:
                description_url += '.' + format
        else:
            params = (('uri', uri.geturl().encode('utf-8')),)
            if format and not strip_format:
                params += (('format', format),)
            # FIXME!
            description_url = u'http://%s/doc/?%s' % (request.META['HTTP_HOST'], urllib.urlencode(params))

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
            
        return {
            'uri': uri,
            'format': format,
            'types': types,
            'show_follow_link': show_follow_link,
            'no_index': no_index,
        }

    @cached_view
    def handle_GET(self, request, context):
        uri, types = context['uri'], context['types']

        graph = self.endpoint.query(get_describe_query(uri, types))
        subject = Resource(uri, graph, self.endpoint)

        if False and with_fragments:
            graph += self.endpoint.query('DESCRIBE ?s WHERE { ?s ?p ?o . FILTER (regex(?s, "^%s#")) }' % uri)

        doc_uri = rdflib.URIRef(self.get_description_url(request, uri, strip_format=True))
        
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
             
            
        context.update({
            'graph': graph,
            'subject': subject,
            'licenses': [Resource(uri, graph, self.endpoint) for uri in licenses],
            'datasets': [Resource(uri, graph, self.endpoint) for uri in datasets],
            'formats': formats,
            'query': graph.query,
        })

        if context['format']:
            try:
                return self.render_to_format(request, context, context['subject'].template_name, context['format'])
            except KeyError:
                raise Http404
        else:
            return self.render(request, context, context['subject'].template_name)


class SparqlView(EndpointView, RDFView, ResultSetView):
    class SparqlViewException(Exception): pass
    class ConcurrentQueryException(SparqlViewException): pass
    class ExcessiveQueryException(SparqlViewException): pass

    def perform_query(self, request, query, common_prefixes):
        client = redis.client.Redis(**settings.REDIS_PARAMS)
        addr = request.META['REMOTE_ADDR']
        if not client.setnx('sparql:lock:%s' % addr, 1):
            raise self.ConcurrentQueryException
        try:
            intensity = float(client.get('sparql:intensity:%s' % addr) or 0)
            last = float(client.get('sparql:last:%s' % addr) or 0)
            intensity = max(0, intensity - (time.time() - last) / 20)
            if intensity > 20:
                raise self.ExcessiveQueryException
            elif intensity > 10:
                time.sleep(intensity - 10)

            start = time.time()
            results = self.endpoint.query(query, timeout=5, common_prefixes=common_prefixes)
            end = time.time()

            client.set('sparql:intensity:%s' % addr, intensity + end - start)
            client.set('sparql:last:%s' % addr, end)

            return results
        finally:
            client.delete('sparql:lock:%s' % addr)
    
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
            results = self.perform_query(request, query, form.cleaned_data['common_prefixes'])
        except urllib2.HTTPError, e:
            context['error'] = e.read() #parse(e).find('.//pre').text
            context['status_code'] = e.code
            return context
        except self.ConcurrentQueryException, e:
            context['error'] = "You cannot perform more than one query at a time.\nPlease wait for your previous query to complete or time out first."
            context['status_code'] = 403
            return context
        except self.ExcessiveQueryException, e:
            context['error'] = "You have been performing a lot of queries recently.\nPlease wait a while and try again."
            context['status_code'] = 403
            return context
        except etree.XMLSyntaxError, e:
            context['error'] = "Your query could not be returned in the time allotted it.\nPlease try a simpler query or using LIMIT to reduce the number of returned results."
            context['status_code'] = 403
            return context

        
        if isinstance(results, list):
            context['results'] = results
        elif isinstance(results, bool):
            context['result'] = results
        elif isinstance(results, rdflib.ConjunctiveGraph):
            context['graph'] = results
            context['subjects'] = results.subjects()

        context['query'] = results.query
        context['duration'] = results.duration
        
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

