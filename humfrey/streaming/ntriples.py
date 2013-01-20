try: # rdflib 3.0
    from rdflib.plugins.parsers.ntriples import NTriplesParser as NTriplesParser_, ParseError
except ImportError: # rdflib 2.4.x
    from rdflib.syntax.parsers.ntriples import NTriplesParser as NTriplesParser_, ParseError

from .base import StreamingParser, StreamingSerializer

__all__ = ['NTriplesSource', 'NTriplesSink']

class NTriplesParser(StreamingParser):
    media_type = 'text/plain'
    format_type = 'graph'

    def get_sparql_results_type(self):
        self.mode = 'parse'
        return 'graph'

    def get_fields(self):
        raise TypeError("This is a graph parser")

    def get_bindings(self):
        raise TypeError("This is a graph parser")

    def get_boolean(self):
        raise TypeError("This is a graph parser")

    def get_triples(self):
        self.mode = 'parse'
        parser = NTriplesParser_()
        parser.sink = self.Sink(self)
        self.triple = None
        while True:
            parser.line = self._stream.readline().strip()
            if not parser.line:
                break
            try:
                parser.parseline()
            except ParseError:
                raise ParseError("Invalid line: %r" % parser.line)
            if self.triple:
                yield self.triple
                self.triple = None

    class Sink(object):
        def __init__(self, source):
            self.source = source
        def triple(self, subject, predicate, object):
            self.source.triple = subject, predicate, object


class NTriplesSerializer(StreamingSerializer):
    media_type = 'text/plain'
    supported_results_types = ('graph',)

    def _iter(self, sparql_results_type, fields, bindings, boolean, triples):
        for triple in triples:
            yield u'{0} {1} {2} .\n'.format(*triple).encode('utf-8')
