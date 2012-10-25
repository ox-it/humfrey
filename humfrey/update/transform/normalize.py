from __future__ import with_statement

from collections import defaultdict
import datetime
import logging
import urllib2
import urlparse

try:
    import json
except ImportError:
    import simplejson as json

from django.conf import settings
import pytz
from rdflib import Literal, BNode, URIRef

from humfrey.update.transform.base import Transform
from humfrey.streaming import RDFSource, RDFXMLSink
from humfrey.utils.namespaces import NS, expand, HUMFREY
from humfrey.sparql.endpoint import Endpoint

logger = logging.getLogger(__name__)

class Normalization(object):
    done = False

class TimezoneNormalization(Normalization):
    def __init__(self, timezone_name):
        self.timezone = pytz.timezone(timezone_name)
    def __call__(self, source):
        tz = self.timezone
        for s, p, o in source:
            if isinstance(o, Literal) and o.datatype == NS.xsd.dateTime:
                try:
                    dt = o.toPython()
                    if isinstance(dt, datetime.datetime) and not dt.tzinfo:
                        o = Literal(tz.localize(dt))
                except Exception:
                    logger.exception("Failed to parse datetime: %s", o)
            yield (s, p, o)
        self.done = True

class SearchNormalization(Normalization):
    def __init__(self, safe_predicates=None):
        self.pass_function = self.find_searches
        self.replacements = {}
        self.mapping = {}
        self.searches = defaultdict(dict)
        self.safe_predicates = frozenset(map(expand, (safe_predicates or ())))
        self.no_index = set()

    def __call__(self, source):
        for triple in self.pass_function(source):
            yield triple

    def find_searches(self, source):
        for s, p, o in source:
            if p == HUMFREY.searchNormalization:
                self.replacements[s] = o
            elif p == HUMFREY.searchQuery:
                self.searches[s]['query'] = unicode(o)
            elif p == HUMFREY.searchType:
                self.searches[s]['type'] = unicode(o)
            else:
                yield s, p, o

        searches = defaultdict(set)
        for s, search in self.searches.iteritems():
            searches[(search.get('type'), search.get('query'))].add(s)

        logger.debug("Performing searches (%d)", len(searches))

        #conn = httplib.HTTPConnection(**settings.ELASTICSEARCH_SERVER)
        #conn.connect()
        for (ptype, query_string), subjects in searches.iteritems():
            if ptype:
                path = '/{store}/{type}/_search'.format(store=self.store.slug,
                                                       type=ptype)
            else:
                path = '/{store}/_search'.format(store=self.store_slug or self.store.slug)

            elasticsearch_url = urlparse.urlunsplit(('http',
                                                     '{host}:{port}'.format(**settings.ELASTICSEARCH_SERVER),
                                                     path, '', ''))

            query = {'query': {'query_string': {'query': query_string.replace('-', '')}}}

            try:
                response = urllib2.urlopen(elasticsearch_url, json.dumps(query))
            except urllib2.HTTPError, e:
                logger.error("HTTP error when searching",
                             exc_info=1,
                             extra={'body': e.read(),
                                    'status': e.code})
                continue

            result = json.load(response)

            if result['hits']['hits']:
                hit = result['hits']['hits'][0]
                logger.info('Mapped "%s" (%s) to "%s" (%s), from %d results',
                            query_string,
                            ptype,
                            hit['_source']['uri'],
                            hit['_source'].get('label'),
                            len(result['hits']['hits']))
                for subject in subjects:
                    self.mapping[subject] = URIRef(hit['_source']['uri'])
            else:
                logger.warning('No match for "%s" (%s)', query_string, ptype)
                self.no_index.update(subjects)

        logger.debug("Searches done")

        self.pass_function = self.substitute_searches

    def substitute_searches(self, source):
        logger.debug("Substituting search results (%d things, %d matches)", len(self.replacements), len(self.mapping))
        for s, p, o in source:
            if s in self.replacements and self.replacements[s] in self.mapping:
                s = self.mapping[self.replacements[s]]
            if o in self.replacements and self.replacements[o] in self.mapping:
                o = self.mapping[self.replacements[o]]
            yield s, p, o
        for subject in self.no_index:
            yield (s, HUMFREY.noIndex, Literal(True))
        logger.debug("Substitutions done")
        self.done = True


class NotationNormalization(Normalization):
    def __init__(self, datatypes, safe_predicates=None):
        self.datatypes = set(map(expand, datatypes))
        self.notations = defaultdict(set)
        self.pass_function = self.find_notations
        self.safe_predicates = frozenset(map(expand, (safe_predicates or ())))
    def __call__(self, source):
        for triple in self.pass_function(source):
            yield triple

    def find_notations(self, source):
        skos_notation, datatypes = NS.skos.notation, self.datatypes
        for s, p, o in source:
            if p == skos_notation and o.datatype in datatypes:
                self.notations[o].add(s)
            yield (s, p, o)
        self.pass_function = self.substitute_notations

    def substitute_notations(self, source):
        if self.notations:
            queries = [("""
            SELECT ?notation ?thing WHERE {{
                VALUES ?notation {{
                  {0}
                }}
                ?thing skos:notation ?notation .
                FILTER (isuri(?thing))
            }}""", "\n                  ", "{0}"), ("""
            SELECT ?notation ?thing WHERE {{
                ?thing skos:notation ?notation .
                FILTER (isuri(?thing))
            }} BINDINGS ?notation {{
                {0}
            }}""", "\n                ", "({0})")]
            for query, delimiter, term in queries:
                query = query.format(delimiter.join(term.format(n.n3()) for n in self.notations))
                try:
                    notation_mapping = dict(self.endpoint.query(query, log_failure=False))
                except urllib2.HTTPError, e:
                    if e.code != 400:
                        raise
                else:
                    break
            else:
                logger.error("SPARQL server doesn't support either VALUES or BINDINGS. Choose a different server platform or remove the 'notations' normalization.")
                self.done = True
                return
        else:
            notation_mapping = {}
        mapping = {}
        self.to_remove = set()

        for notation in self.notations:
            for subject in self.notations[notation]:
                if notation in notation_mapping:
                    mapping[subject] = notation_mapping[notation]
                else:
                    mapping[subject] = None
                    logger.warning("Notation %s for %s not found.", notation, subject)

        for s, p, o in source:
            if mapping.get(s) is not None:
                s = mapping[s]
                if p not in self.safe_predicates and isinstance(o, (BNode, URIRef)):
                    # Start the process of removing the CBD for s.
                    self.to_remove.add(o)
                    continue
            elif s in mapping:
                yield (s, HUMFREY.noIndex, Literal(True))

            if mapping.get(o) is not None:
                o = mapping[o]
            elif s in mapping:
                yield (o, HUMFREY.noIndex, Literal(True))

            yield (s, p, o)

        if self.to_remove:
            self.pass_function = self.remove_bounded_description
        else:
            self.done = True

    def remove_bounded_description(self, source):
        to_remove = set()
        for s, p, o in source:
            if s in self.to_remove:
                if isinstance(o, (BNode, URIRef)):
                    to_remove.add(o)
            else:
                yield (s, p, o)
        if to_remove:
            self.to_remove = to_remove
        else:
            self.done = True

class Normalize(Transform):
    available_normalizations = {'timezones': TimezoneNormalization,
                                'notations': NotationNormalization,
                                'search': SearchNormalization}

    def __init__(self, **kwargs):
        self.normalizations = []
        for key in kwargs:
            normalization = self.available_normalizations[key](**kwargs[key])
            self.normalizations.append(normalization)

    def execute(self, transform_manager, input):
        transform_manager.start(self, [])

        endpoint = Endpoint(transform_manager.store.query_endpoint)

        for normalization in self.normalizations:
            normalization.endpoint = endpoint
            normalization.store = transform_manager.store

        while self.normalizations:
            with open(input, 'r') as source:
                pipeline = RDFSource(source)
                for normalization in self.normalizations:
                    pipeline = normalization(pipeline)
                with open(transform_manager('rdf'), 'w') as target:
                    RDFXMLSink(target, triples=pipeline)

            input = target.name
            self.normalizations = [n for n in self.normalizations if not n.done]

        return input
