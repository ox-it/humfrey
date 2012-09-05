import re
import urllib
import urlparse
try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs

import rdflib

from django.conf import settings
from django.core.urlresolvers import reverse

if 'django_hosts' in settings.INSTALLED_APPS:
    from django_hosts.reverse import reverse_full
    with_hosts = True
else:
    def reverse_full(host, *args, **kwargs):
        return reverse(*args, **kwargs)
    with_hosts = False

from .mappingconf import get_id_mapping, get_doc_view, get_desc_view

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

    if isinstance(uri, unicode):
        encoded_uri = uri.encode('utf-8')
    else:
        encoded_uri = urllib.unquote(uri)

    for id_prefix, doc_prefix, _ in get_id_mapping():
        if uri.startswith(id_prefix):
            base = doc_prefix + urllib.quote(encoded_uri[len(id_prefix):])
            pattern = base.replace('%', '%%') + '.%(format)s'
            return DocURLs(base, pattern)

    if graph and not described and any(graph.triples((uri, None, None))):
        described = True

    if described == False:
        return DocURLs(encoded_uri, encoded_uri.replace('%', '%%'))

    view_name = get_doc_view() if described else get_desc_view()

    base = '%s?%s' % (reverse_full(*view_name),
                      urllib.urlencode((('uri', encoded_uri),)))

    return DocURLs(base,
                   '%s&format=%%(format)s' % base.replace('%', '%%'))

def doc_forward(uri, graph=None, described=None, format=None):
    return doc_forwards(uri, graph, described)[format]

BACKWARD_FORMAT_RE = re.compile(r'^(?P<url>.*?)(?:\.(?P<format>[a-z\d]+))?$')

def doc_backward(url, formats=None):
    parsed_url = urlparse.urlparse(url)
    query = parse_qs(parsed_url.query)
    host_path = '//{0}{1}'.format(parsed_url.netloc, parsed_url.path)
    if host_path == reverse_full(*get_doc_view()):
        return rdflib.URIRef(query.get('uri', [None])[0]), query.get('format', [None])[0], False

    match = BACKWARD_FORMAT_RE.match(url)
    url, format = match.group('url'), match.group('format')
    if format and formats is not None and format not in formats:
        url, format = '%s.%s' % (url, format), None
    
    if with_hosts:
        url_part = url
    else:
        url_part = urlparse.urlparse(url).path

    for id_prefix, doc_prefix, is_local in get_id_mapping():
        doc_prefix = urlparse.urljoin(url, doc_prefix)
        if url_part.startswith(doc_prefix):
            url_part = id_prefix + url_part[len(doc_prefix):]
            return rdflib.URIRef(urllib.unquote(url_part)), format, is_local
    else:
        return None, None, None
