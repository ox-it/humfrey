from __future__ import with_statement

from collections import defaultdict
import logging

from django.conf import settings
import pytz
from rdflib import Literal, BNode, URIRef

from humfrey.update.transform.base import Transform
from humfrey.streaming import RDFSource, RDFXMLSink
from humfrey.utils.namespaces import NS, expand
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
                    if not dt.tzinfo:
                        o = Literal(tz.localize(dt))
                except Exception:
                    logger.exception("Failed to parse datetime: %s", o)
            yield (s, p, o)
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
            query = """SELECT ?notation ?thing WHERE {
                ?thing skos:notation ?notation
            } BINDINGS ?notation {
                %s
            }"""
            query = query % '\n'.join('(%s)' % n.n3() for n in self.notations)
            print '=' * 80
            print query
            print '=' * 80
            notation_mapping = dict(self.endpoint.query(query))
        else:
            notation_mapping = {}
        mapping = {}
        self.to_remove = set()

        for notation in self.notations:
            for subject in self.notations[notation]:
                if notation in notation_mapping:
                    mapping[subject] = notation_mapping[notation]
                else:
                    logger.warning("Notation %s for %s not found.", notation, subject)

        for s, p, o in source:
            if o in mapping:
                yield (s, p, mapping[o])
            elif s in mapping:
                if p not in self.safe_predicates and isinstance(o, (BNode, URIRef)):
                    self.to_remove.add(o)
            else:
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
                                'notations': NotationNormalization}

    def __init__(self, **kwargs):
        self.store = kwargs.pop('store', None)
        self.normalizations = []
        for key in kwargs:
            normalization = self.available_normalizations[key](**kwargs[key])
            self.normalizations.append(normalization)

    def execute(self, transform_manager, input):
        transform_manager.start(self, [])

        if self.store:
            store = self.get_store(transform_manager, self.store, update=True)
            endpoint_query = store.query_endpoint
        else:
            endpoint_query = settings.ENDPOINT_QUERY
        endpoint = Endpoint(endpoint_query)

        for normalization in self.normalizations:
            normalization.endpoint = endpoint

        while self.normalizations:
            with open(input, 'r') as source:
                pipeline = RDFSource(source)
                for normalization in self.normalizations:
                    pipeline = normalization(pipeline)
                with open(transform_manager('rdf'), 'w') as target:
                    sink = RDFXMLSink(pipeline)
                    sink.serialize(target)

            input = target.name
            self.normalizations = [n for n in self.normalizations if not n.done]

        return input
