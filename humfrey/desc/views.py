import logging
import re
import urlparse

import rdflib

from django.conf import settings
from django.http import Http404, HttpResponsePermanentRedirect
from django.utils.importlib import import_module
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import resolve, Resolver404

from django_conneg import decorators
from django_conneg.views import HTMLView, ContentNegotiatedView
from django_conneg.http import HttpResponseSeeOther, HttpResponseTemporaryRedirect, MediaType

from humfrey.linkeddata.resource import Resource, IRI
from humfrey.linkeddata.uri import doc_forward, doc_backward
from humfrey.linkeddata.views import MappingView

from humfrey.results.views.standard import RDFView
from humfrey.sparql.views import StoreView
from humfrey.utils.namespaces import NS, expand

logger = logging.getLogger(__name__)

class IdView(MappingView, StoreView, ContentNegotiatedView):
    id_mapping_redirects = tuple((re.compile(a), b, frozenset(c)) for a,b,c in getattr(settings, 'ID_MAPPING_REDIRECTS', ()))

    if 'django_hosts' in settings.INSTALLED_APPS:
        from django_hosts.middleware import HostsMiddleware
        hosts_middleware = HostsMiddleware()

    def get(self, request):
        uri = rdflib.URIRef(request.build_absolute_uri())
        if not IRI.match(uri):
            raise Http404
        if not self.get_types(uri):
            raise Http404

        description_url = doc_forward(uri, described=True)

        for pattern, target, mimetypes in self.id_mapping_redirects:
            match = pattern.match(str(uri))
            if match and self.override_redirect(request, description_url, mimetypes):
                description_url = target % match.groupdict()
                break

        return HttpResponseSeeOther(description_url)

    def override_redirect(self, request, description_url, mimetypes):
        url = urlparse.urlparse(description_url)
        if 'django_hosts' in settings.INSTALLED_APPS:
            host, _ = self.hosts_middleware.get_host(url.netloc)
            urlconf = host.urlconf
        else:
            urlconf = None

        try:
            view, _, _ = resolve(url.path, urlconf)
        except Resolver404:
            return False

        should_redirect = lambda: True
        renderer = decorators.renderer(None, mimetypes, float('inf'), None)(should_redirect)

        accepts = self.parse_accept_header(request.META.get('HTTP_ACCEPT', ''))
        renderers = MediaType.resolve(accepts, (renderer,) + view._renderers)

        return renderers and renderers[0] is should_redirect

class DescView(MappingView, StoreView):
    """
    Will redirect to DocView if described by endpoint, otherwise to the URI given.

    Allows us to be lazy when determining whether to go on- or off-site.
    """
    def get(self, request):
        uri = rdflib.URIRef(request.GET.get('uri', ''))
        try:
            url = urlparse.urlparse(uri)
        except Exception:
            raise Http404
        if not IRI.match(uri):
            return HttpResponseTemporaryRedirect(unicode(uri))
        elif request.GET.get('source') == 'purl':
            return HttpResponseSeeOther(doc_forward(uri, described=True))
        elif self.get_types(uri):
            return HttpResponsePermanentRedirect(doc_forward(uri, described=True))
        elif url.scheme in ('http', 'https') and url.netloc and url.path.startswith('/'):
            return HttpResponseTemporaryRedirect(unicode(uri))
        else:
            raise Http404

class DocView(MappingView, StoreView, RDFView, HTMLView):
    check_canonical = True

    doc_rdf_processors = getattr(settings, 'DOC_RDF_PROCESSORS', ())
    template_name = 'doc/base'
    template_overrides = ()

    def __init__(self, *args, **kwargs):
        self._doc_rdf_processors_cache = None
        super(DocView, self).__init__(*args, **kwargs)

    def get(self, request):
        additional_headers = {}
        doc_url = request.build_absolute_uri()

        uri, format, is_local = doc_backward(doc_url, set(self._renderers_by_format))
        if not uri:
            logger.debug("Could not resolve URL to a URI: %r", doc_url)
            raise Http404

        expected_doc_url = doc_forward(uri, request, format=format, described=True)

        types = self.get_types(uri)
        if not types:
            logger.debug("Resource has no type, so is probably not known in these parts: %r", uri)
            raise Http404

        if self.check_canonical and expected_doc_url != doc_url:
            logger.debug("Request for a non-canonical doc URL (%r) for %r, redirecting to %r", doc_url, uri, expected_doc_url)
            return HttpResponsePermanentRedirect(expected_doc_url)

        # If no format was given explicitly (i.e. format parameter or
        # extension) we inspect the Content-Type header.
        if not format:
            renderers = self.get_renderers(request)
            if renderers:
                format = renderers[0].format
                expected_doc_url = doc_forward(uri, request, format=format, described=True)
        if expected_doc_url != doc_url:
            additional_headers['Content-Location'] = expected_doc_url

        doc_uri = rdflib.URIRef(doc_forward(uri, request, format=None, described=True))

        context = {
            'subject_uri': uri,
            'doc_uri': doc_uri,
            'format': format,
            'types': types,
            'show_follow_link': not is_local,
            'no_index': not is_local,
            'additional_headers': additional_headers,
        }

        subject_uri, doc_uri = context['subject_uri'], context['doc_uri']
        types = context['types']

        queries, graph = [], rdflib.ConjunctiveGraph()
        for prefix, namespace_uri in NS.iteritems():
            graph.namespace_manager.bind(prefix, namespace_uri)

        graph += ((subject_uri, NS.rdf.type, t) for t in types)
        subject = Resource(subject_uri, graph, self.endpoint)

        for query in subject.get_queries():
            graph += self.endpoint.query(query)
            queries.append(query)

        licenses, datasets = set(), set()
        for graph_name in graph.subjects(NS['ov'].describes):
            graph.add((doc_uri, NS['dcterms'].source, graph_name))
            licenses.update(graph.objects(graph_name, NS['dcterms'].license))
            datasets.update(graph.objects(graph_name, NS['void'].inDataset))

        if len(licenses) == 1:
            for license_uri in licenses:
                graph.add((doc_uri, NS['dcterms'].license, license_uri))

        if not graph:
            logger.debug("Graph for %r was empty; 404ing", uri)
            raise Http404

        for doc_rdf_processor in self._doc_rdf_processors:
            additional_context = doc_rdf_processor(request=request,
                                                   graph=graph,
                                                   doc_uri=doc_uri,
                                                   subject_uri=subject_uri,
                                                   subject=subject,
                                                   endpoint=self.endpoint,
                                                   renderers=self._renderers)
            if additional_context:
                context.update(additional_context)

        context.update({
            'graph': graph,
            'subject': subject,
            'licenses': [Resource(uri, graph, self.endpoint) for uri in licenses],
            'datasets': [Resource(uri, graph, self.endpoint) for uri in datasets],
            'queries': queries,
            'template_name': subject.template_name,
        })

        template_name = subject.template_name or self.template_name
        for template_override in self.template_overrides:
            tn, types = template_override[0], template_override[1:]
            print tn, types, subject.get_all('rdf:type')
            if set(subject._graph.objects(subject._identifier, NS.rdf.type)) & set(map(expand, types)):
                template_name = tn
                break

        if context['format']:
            try:
                return self.render_to_format(request, context, template_name, format)
            except KeyError:
                raise Http404
        else:
            return self.render(request, context, template_name)

    @property
    def _doc_rdf_processors(self):
        if self._doc_rdf_processors_cache is not None:
            return self._doc_rdf_processors_cache
        processors = []
        for name in settings.DOC_RDF_PROCESSORS:
            module_name, attribute_name = name.rsplit('.', 1)
            try:
                module = import_module(module_name)
            except ImportError, e:
                raise ImproperlyConfigured('Error importing doc RDF processor module %s: "%s"' % (module_name, e))
            try:
                processors.append(getattr(module, attribute_name))
            except AttributeError:
                raise ImproperlyConfigured('Module "%s" does not define a "%s" callable doc RDF processor' % (module_name, attribute_name))
        self._doc_rdf_processors_cache = tuple(processors)
        return self._doc_rdf_processors_cache


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

