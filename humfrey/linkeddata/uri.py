import re
import urllib.error
import urllib.parse
import urllib.request

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
    of uri. described is a ternary boolean (None for 'unknown').
    """

    if isinstance(uri, str):
        encoded_uri = uri.encode('utf-8')
    else:
        encoded_uri = urllib.parse.unquote(uri)

    for id_prefix, doc_prefix, _ in get_id_mapping():
        if uri.startswith(id_prefix):
            base = doc_prefix + urllib.parse.quote(encoded_uri[len(id_prefix):])
            pattern = base.replace('%', '%%') + '.%(format)s'
            return DocURLs(base, pattern)

    if graph is not None and not described and any(graph.triples((uri, None, None))):
        described = True

    if described == False:
        return DocURLs(encoded_uri, encoded_uri.replace('%', '%%'))

    url = get_doc_view() if described else get_desc_view()
    if isinstance(url, tuple):
        # This used to return a tuple, now it returns the URL directly
        url = reverse_full(*url)

    params = [('uri', encoded_uri)]
    if not described:
        from humfrey.desc.views import DescView
        params.append(('token', DescView.get_uri_token(encoded_uri)))

    base = '%s?%s' % (url, urllib.parse.urlencode(params))
    print(base)

    return DocURLs(base,
                   '%s&format=%%(format)s' % base.replace('%', '%%'))

def doc_forward(uri, graph=None, described=None, format=None):
    return doc_forwards(uri, graph, described)[format]

BACKWARD_FORMAT_RE = re.compile(r'^(?P<url>.*?)(?:\.(?P<format>[a-z\d\-]+))?$')

def _get_host_path(url):
    parsed_url = urllib.parse.urlparse(url)
    return '//{0}{1}'.format(parsed_url.netloc, parsed_url.path)

def doc_backward(url, formats=None):
    """
    Determines the URI a doc page is about.

    Returns a tuple of (uri, format, canonical).
    """
    parsed_url = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed_url.query)
    doc_view_url = get_doc_view()
    if isinstance(doc_view_url, tuple):
        doc_view_url = reverse_full(*doc_view_url)
    if _get_host_path(url) == urllib.parse.urljoin(_get_host_path(url), doc_view_url):
        return rdflib.URIRef(query.get('uri', [None])[0] or ''), query.get('format', [None])[0], False

    match = BACKWARD_FORMAT_RE.match(url)
    url, format = match.group('url'), match.group('format')
    if format and formats is not None and format not in formats:
        url, format = '%s.%s' % (url, format), None

    if with_hosts:
        url_part = url
    else:
        url_part = urllib.parse.urlparse(url).path

    for id_prefix, doc_prefix, is_local in get_id_mapping():
        doc_prefix = urllib.parse.urljoin(url, doc_prefix)
        if url_part.startswith(doc_prefix):
            url_part = id_prefix + url_part[len(doc_prefix):]
            return rdflib.URIRef(urllib.parse.unquote(url_part)), format, is_local
    else:
        return None, None, None
