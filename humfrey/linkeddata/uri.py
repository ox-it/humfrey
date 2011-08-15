import re
import urllib
import urlparse
try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs

import rdflib

from django.conf import settings

from django_hosts.reverse import reverse_crossdomain

class DocURLs(object):
    def __init__(self, base, format_pattern):
        self._base = base
        self._format_pattern = format_pattern
    def __getitem__(self, format):
        if format is None:
            return self._base
        else:
            return self._format_pattern % {'format': format}

def doc_forwards(uri, graph=None, described=None):
    """
    Determines all doc URLs for a URI.

    graph is an rdflib.ConjunctiveGraph that can be checked for a description
    of uri. described is a ternary boolean.
    """

    for id_prefix, doc_prefix, _ in settings.ID_MAPPING:
        if uri.startswith(id_prefix):
            base = doc_prefix + uri[len(id_prefix):]
            pattern = base.replace('%', '%%') + '.%(format)s'
            return DocURLs(base, pattern)

    if graph and not described and any(graph.triples((uri, None, None))):
        described = True

    if described == False:
        return DocURLs(unicode(uri), unicode(uri).replace('%', '%%'))

    if described == True:
        view_name = 'doc-generic'
    else:
        view_name = 'desc'

    base = 'http:%s?%s' % (reverse_crossdomain('data', view_name),
                                 urllib.urlencode((('uri', uri.encode('utf-8')),)))
    
    return DocURLs(base,
                   '%s&format=%%(format)s' % base.replace('%', '%%'))

def get_format(view, request):
    renderers = view.get_renderers(request)
    if renderers:
        return renderers[0].format

def doc_forward(uri, view=None, request=None, graph=None, described=None, format=None):

    if view and request and not format:
        format = get_format(view, request)

    return doc_forwards(uri, graph, described)[format]

BACKWARD_FORMAT_RE = re.compile(r'(?P<url>.*?)(?:\.(?P<format>[a-z]+))?')

def doc_backward(url, view=None, request=None):
    if view and request:
        format = get_format(request)
    else:
        format = None
    parsed_url = urlparse.urlparse(url)
    query = parse_qs(parsed_url.query)
    if url.split(':', 1)[-1].split('?')[0] == reverse_crossdomain('data', 'doc-generic'):
        return rdflib.URIRef(query.get('uri', [None])[0]), query.get('format', [None])[0], False
    
    match = BACKWARD_FORMAT_RE.match(url)
    url, format = match.group('url'), match.group('format')
    for id_prefix, doc_prefix, is_local in settings.ID_MAPPING:
        if url.startswith(doc_prefix):
            url = id_prefix + url[len(doc_prefix):]
            return rdflib.URIRef(url), format, is_local
    else:
        return None, None, None
