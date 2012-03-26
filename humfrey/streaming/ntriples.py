from rdflib.plugins.parsers.ntriples import NTriplesParser, ParseError
from rdflib.plugins.serializers.nt import NTSerializer

__all__ = ['NTriplesSource', 'NTriplesSink']

class NTriplesSource(NTriplesParser):
    class Sink(object):
        def __init__(self, source):
            self.source = source
        def triple(self, subject, predicate, object):
            self.source.triple = subject, predicate, object

    def __init__(self, f):
        self.file = f
        self.triple = None
        super(NTriplesSource, self).__init__(self.Sink(self))

    def __iter__(self):
        self.buffer = ''
        while True:
            self.line = self.readline()
            if self.line is None:
                break
            try:
                self.parseline()
            except ParseError:
                raise ParseError("Invalid line: %r" % self.line)
            if self.triple:
                yield self.triple
                self.triple = None

NTriplesSink = NTSerializer
