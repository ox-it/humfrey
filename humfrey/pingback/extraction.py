"""
Contains functions with extract triples from external resources.
"""

from __future__ import with_statement

import functools
import urlparse

import lxml
import pytz
import rdflib

from django.conf import settings
from humfrey.utils.namespaces import NS

__all__ = ['extractors']

class NoLinkFoundError(Exception):
    pass

class InvalidPingback(Exception):
    def __init__(self, reason):
        self.reason = reason

def _extract_from_rdf(graph, response, filename, source, target, format):
    pass

def _extract_from_html(graph, response, filename, source, target):
    try:
        html = lxml.etree.parse(response, parser=lxml.etree.HTMLParser())
    except:
        raise InvalidPingback('invalid-html')

    url = response['content-location']

    for anchor in html.xpath(".//a"):
        href = urlparse.urlparse(urlparse.urljoin(url, anchor.get('href')))
        if not href[2]:
            href = href[:2] + ('/',) + href[3:]
        href = urlparse.urlunparse(href)
        if href == target:
            break
    else:
        raise NoLinkFoundError


    title = html.xpath('.//head/title')
    if title and title[0].text:
        graph.add((rdflib.URIRef(url), NS.dcterms['title'], rdflib.Literal(title[0].text)))

extractors = {'application/rdf+xml': functools.partial(_extract_from_rdf, format='xml'),
              'text/n3': functools.partial(_extract_from_rdf, format='n3'),
              'text/turtle': functools.partial(_extract_from_rdf, format='n3'),
              'text/plain': functools.partial(_extract_from_rdf, format='nt'),
              'application/xhtml+xml': _extract_from_html,
              'text/html': _extract_from_html,
              }

def extract(pingback, response):
    content_type = response.get('content-type', '').split(';')[0].lower()

    graph = rdflib.ConjunctiveGraph()
    graph_name = pingback.graph_name

    date = lambda x: rdflib.Literal(pytz.timezone(settings.TIME_ZONE).localize(x))
    
    url = response['content-location']
    uri = rdflib.URIRef(url)

    graph += (
        (uri, NS.sioc.links_to, rdflib.URIRef(pingback.target)),
        (graph_name, NS.dcterms.created, date(pingback.created)),
        (graph_name, NS.dcterms.modified, date(pingback.updated)),
        (graph_name, NS.dcterms.source, uri),
        (graph_name, NS.void.inDataset, settings.PINGBACK_DATASET),
        (graph_name, NS.dcterms['title'], rdflib.Literal(u'Pingback from %s to %s' % (unicode(pingback.source), unicode(pingback.target)))),
    )

    try:
        extractor = extractors[content_type]
    except KeyError:
        raise InvalidPingback('unexpected-media-type')

    try:
        extractor(graph, response, pingback.source, pingback.target)
    except NoLinkFoundError:
        raise InvalidPingback('no-link-found')

    return graph

