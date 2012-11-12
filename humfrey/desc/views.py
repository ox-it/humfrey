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
from humfrey.sparql.utils import get_labels

from humfrey.results.views.json import JSONRDFView
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
            raise Http404("Invalid IRI")
        if not self.get_types(uri):
            raise Http404("URI has no types; not known around here")

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
        renderers = MediaType.resolve(accepts, (renderer,) + view.conneg.renderers)

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

class DocView(MappingView, StoreView, RDFView, JSONRDFView, HTMLView):
    check_canonical = True

    doc_rdf_processors = getattr(settings, 'DOC_RDF_PROCESSORS', ())
    template_name = 'doc/base'
    template_overrides = ()

    def __init__(self, *args, **kwargs):
        self._doc_rdf_processors_cache = None
        super(DocView, self).__init__(*args, **kwargs)

    def get(self, request):
        additional_headers = {}

        # Apache helpfully(!?) unescapes encoded hash characters. If we get one
        # we know that the browser sent a '%23' (or else would have stripped it
        # as a fragment identifier. We replace it with a '%23' so that our URI
        # canonicalisation doesn't get stuck in an endless redirect loop.
        doc_url = request.build_absolute_uri().replace('#', '%23')

        # Given a URL 'http://example.org/doc/foo.bar' we check whether 'foo',
        # has a type (ergo 'bar' is a format), and if not we assume that
        # 'foo.bar' is part of the URI
        for formats in (None, ()):
            uri, format, is_local = doc_backward(doc_url, formats)
            if not IRI.match(uri):
                raise Http404("Invalid IRI")
            if not uri:
                logger.debug("Could not resolve URL to a URI: %r", doc_url)
                raise Http404("Could not resolve URL to a URI")
            types = self.get_types(uri)
            if types:
                break
            doc_url = doc_url.rsplit('.', 1)[0]
        else:
            logger.debug("Resource has no type, so is probably not known in these parts: %r", uri)
            raise Http404("Resource has no type, so is probably not known in these parts")

        expected_doc_url = urlparse.urljoin(doc_url, doc_forward(uri, request, format=format, described=True))
        if self.check_canonical and expected_doc_url != doc_url:
            logger.debug("Request for a non-canonical doc URL (%r) for %r, redirecting to %r", doc_url, uri, expected_doc_url)
            return HttpResponsePermanentRedirect(expected_doc_url)

        doc_uri = rdflib.URIRef(doc_forward(uri, request, format=None, described=True))

        self.context.update({
            'subject_uri': uri,
            'doc_uri': doc_uri,
            'format': format,
            'types': types,
            'show_follow_link': not is_local,
            'no_index': not is_local,
            'additional_headers': additional_headers,
        })

        subject_uri, doc_uri = self.context['subject_uri'], self.context['doc_uri']
        types = self.context['types']

        queries, graph = [], rdflib.ConjunctiveGraph()
        for prefix, namespace_uri in NS.iteritems():
            graph.namespace_manager.bind(prefix, namespace_uri)

        graph += ((subject_uri, NS.rdf.type, t) for t in types)
        subject = Resource(subject_uri, graph, self.endpoint)

        for query in subject.get_queries():
            graph += self.endpoint.query(query)
            queries.append(query)
        graph += get_labels(graph, self.endpoint, mapping=False)

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
            raise Http404("Graph was empty")

        self.template_name = subject.template_name or self.template_name
        for template_override in self.template_overrides:
            tn, types = template_override[0], template_override[1:]
            if set(subject._graph.objects(subject._identifier, NS.rdf.type)) & set(map(expand, types)):
                self.template_name = tn
                break

        self.context.update({
            'graph': graph,
            'subject': subject,
            'licenses': [Resource(uri, graph, self.endpoint) for uri in licenses],
            'datasets': [Resource(uri, graph, self.endpoint) for uri in datasets],
            'queries': map(self.endpoint.normalize_query, queries),
            'template_name': self.template_name,
        })

        self.set_renderers()

        for doc_rdf_processor in self._doc_rdf_processors:
            additional_context = doc_rdf_processor(self.request, self.context)
            if additional_context:
                self.context.update(additional_context)

        # If no format was given explicitly (i.e. format parameter or
        # extension) we inspect the Content-Type header.
        if not format:
            if request.renderers:
                format = request.renderers[0].format
                expected_doc_url = doc_forward(uri, request, format=format, described=True)
        if expected_doc_url != doc_url:
            additional_headers['Content-Location'] = expected_doc_url

        # NOTE: This getattrs every atttr on subject, so would force
        # memoization on any cached attributes. We call it as late as
        # possible to make sure the graph won't change afterwards, making
        # those cached results incorrect.
        self.conneg += subject

        if self.context['format']:
            try:
                return self.render_to_format(format=format)
            except KeyError:
                raise Http404
        else:
            return self.render()

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

    def url_for_format(self, request, format):
        if 'subject_uri' in self.context:
            return doc_forward(self.context['subject_uri'], described=True, format=format)
        else:
            return super(DocView, self).url_for_format(request, format)

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

