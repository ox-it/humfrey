from collections import defaultdict
import logging
import sys
import time
import urllib.request, urllib.parse, urllib.error

import rdflib
try:
    import simplejson as json
except ImportError:
    import json

from humfrey.utils.namespaces import NS
from humfrey.linkeddata.resource import Resource
from humfrey import streaming
from humfrey.utils.user_agents import USER_AGENTS
from humfrey.utils.statsd import statsd

def is_qname(uri):
    return len(uri.split(':')) == 2 and '/' not in uri.split(':')[1]


logger = logging.getLogger(__name__)


class QueryError(Exception):
    def __init__(self, message, status_code):
        self.message = message
        self.status_code = status_code


def trim_indentation(s):
    """Taken from PEP-0257"""
    if not s:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = s.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)


class Endpoint(object):
    _supported_media_types = ['application/sparql-results+xml',
                              'application/sparql-results+json',
                              'text/plain',
                              'text/turtle',
                              'text/n3',
                              'application/rdf+xml']
    def __init__(self, url, update_url=None, namespaces={}, preferred_media_types=()):
        self._url, self._update_url = url, update_url
        self._namespaces = NS.copy()
        self._namespaces.update(namespaces)
        self._cache = defaultdict(dict)

        self._accept_header = self._get_accept_header(preferred_media_types or self._supported_media_types)

    def _get_accept_header(self, preferred_media_types=()):
        # We're quickest at parsing N-Triples (text/plain), then Turtle, then RDF/XML
        # See http://blogs.oucs.ox.ac.uk/opendata/2012/12/05/benchmarking-rdflib-parsers/
        # for crude benchmarking. We put the SRX/SRJ ones first to avoid getting
        # text/plain responses for non-RDF-returning queries.
        media_types = []
        for media_type in preferred_media_types:
            if media_type not in self._supported_media_types:
                media_types.extend(['application/sparql-results+xml',
                                    'text/plain'])
                break
            media_types.append(media_type)
        accept_header = media_types[:]
        for media_type in reversed(media_types):
            accept_header.remove(media_type)
            accept_header.insert(0, media_type)
        return ', '.join('%s;q=%3.1f' % (imt, 1-i/10.0) for i, imt in enumerate(accept_header))

    def normalize_query(self, query, common_prefixes=True):
        query = trim_indentation(query)
        if common_prefixes:
            q = ['\n', query]
            prefixes = []
            for prefix, uri in self._namespaces.items():
                if '%s:' % prefix in query:
                    prefixes.append((prefix, uri))
            prefixes.sort()
            prefixes = ['PREFIX %s: <%s>\n' % i for i in prefixes]
            query = ''.join(prefixes + q)
        return query

    def query(self, query, common_prefixes=True, timeout=None, log_failure=True, preferred_media_types=None, defer=False):
        original_query = query
        query = self.normalize_query(query, common_prefixes)

        request = urllib.request.Request(self._url, urllib.parse.urlencode({
            'query': query,
        }).encode())

        if not defer:
            # Pick the quickest to parse, as it will never be passed through
            # verbatim.
            preferred_media_types = self._supported_media_types
        if preferred_media_types:
            request.add_header('Accept', self._get_accept_header(preferred_media_types))
        else:
            request.add_header('Accept', self._accept_header)
        request.add_header('User-Agent', USER_AGENTS['agent'])
        if timeout:
            request.add_header('Timeout', str(timeout))

        start_time = time.time()

        try:
            logging.debug("Querying %r", self._url)
            try:
                response = urllib.request.urlopen(request)
            except urllib.error.HTTPError as e:
                error_content = e.read()
                raise QueryError(error_content, e.code) from e

            time_to_start = time.time() - start_time

            content_type, params = response.headers.get('Content-Type', 'application/rdf+xml'), {}
            if ';' in content_type:
                content_type, params_ = content_type.split(';', 1)
                for param in params_.split(';'):
                    if '=' in param:
                        params.__setitem__(*param.split('=', 1))
            encoding = params.get('charset', 'UTF-8')
            if content_type in streaming.parsers:
                result = streaming.parsers[content_type](response, encoding)
            else:
                raise AssertionError("Unexpected content-type: %s" % content_type)
            result.query = query
            result.duration = time.time() - start_time
            if not defer:
                result = result.get()
            logger.debug("SPARQL query: %r; took %.2f (%.2f) seconds\n", original_query, time.time() - start_time, time_to_start)
            statsd.timing('humfrey.sparql-query.duration', (time.time() - start_time)*1000)
            statsd.incr('humfrey.sparql-query.success')
            return result
        except Exception:
            try:
                (logger.error if log_failure else logger.debug)(
                    "Failed query: %r; took %.2f seconds", original_query, time.time() - start_time,
                    exc_info=1)
            except UnboundLocalError:
                pass
            statsd.incr('humfrey.sparql-query.fail')
            raise

    def update(self, query):
        request = urllib.request.Request(self._update_url, urllib.parse.urlencode({
            'request': self._namespaces + query.encode('UTF-8'),
        }))
        request.headers['User-Agent'] = 'sparql.py'

        urllib.request.urlopen(request)

    def insert_data(self, triples, graph=None):
        triples = ' . '.join(' '.join(map(self.quote, triple)) for triple in triples)
        triples = "GRAPH %s { %s }" % (self.quote(graph), triples) if graph else triples
        return self.update("INSERT DATA { %s }" % triples)

    def delete_data(self, triples, graph=None):
        triples = ' . '.join(' '.join(map(self.quote, triple)) for triple in triples)
        triples = "GRAPH %s { %s }" % (self.quote(graph), triples) if graph else triples
        return self.update("DELETE DATA { %s }" % triples)

    def clear(self, graph):
        return self.update("CLEAR GRAPH %s" % self.quote(graph))


    def describe(self, uri):
        return self.query("DESCRIBE <%s>" % uri)
    def ask(self, uri):
        return self.query("ASK WHERE { %s ?p ?o }" % uri.n3())

    def forward(self, subject, predicate=None):
        subject, predicate = self.quote(subject), self.quote(predicate)
        if predicate:
            return self.query("SELECT ?object WHERE { %s %s ?object }" % (subject, predicate))
        else:
            return self.query("SELECT ?predicate ?object WHERE { %s ?predicate ?object }" % subject)

    def backward(self, predicate, obj=None):
        if not obj:
            obj, predicate = predicate, None
        predicate, obj = self.quote(predicate), self.quote(obj)
        if predicate:
            return self.query("SELECT ?subject WHERE { ?subject %s %s }" % (predicate, obj))
        else:
            return self.query("SELECT ?subject ?predicate WHERE { ?subject ?predicate %s }" % obj)

    def get(self, uri):
        return Resource(self, uri)

    def quote(self, uri):
        if isinstance(uri, rdflib.term.Node):
            return uri.n3()
        elif not uri:
            return uri
        elif is_qname(uri):
            return uri
        else:
            return '<%s>' % uri

    def __contains__(self, obj):
        if isinstance(obj, tuple):
            return self.query("ASK WHERE { %s }" % ' '.join(map(self.quote, obj)))
        else:
            return self.query("ASK WHERE { %s ?p ?o }" % self.quote(obj))
