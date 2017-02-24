import abc
import types

import rdflib

from humfrey.sparql.results import SparqlResultList
from humfrey.utils.namespaces import NS

from humfrey.utils.statsd import statsd


class ModeError(Exception):
    def __init__(self, previous_mode, new_mode):
        self.previous_mode, self.new_mode = previous_mode, new_mode

    def __repr__(self):
        return 'ModeError({!r}, {!r})'.format(self.previous_mode, self.new_mode)


class StreamingParser(object, metaclass=abc.ABCMeta):
    """
    Base class for streaming parsers.

    These expose the underlying stream as file-like objects, or can be
    used to parse the stream, but not both.
    """

    def __init__(self, stream, encoding='utf-8'):
        self._stream, self._encoding = stream, encoding
        self._mode, self._cached_get = None, None

    @property
    def mode(self):
        return self._mode
    @mode.setter
    def mode(self, mode):
        if self._mode == mode:
            return
        elif self._mode is not None:
            raise ModeError(self._mode, mode)
        else:
            self._mode = mode

    @abc.abstractproperty
    def media_type(self):
        """
        The internet media type of the underlying stream.

        Use this to work out if the stream can be passed on unparsed.
        """

    @abc.abstractproperty
    def format_type(self):
        """
        Either 'sparql-results' or 'graph'.
        """

    @abc.abstractmethod
    def get_sparql_results_type(self):
        """
        Returns the type of thing being parsed.

        Possible return values are ['resultset', 'boolean', 'graph']. These
        correspond to the methods get_bindings(), get_boolean() and
        get_triples() respectively. Calling this method starts parsing the
        stream, so you can no longer use read() or __iter__().
        """

    @abc.abstractmethod
    def get_fields(self):
        """
        Returns a list of field names for a resultset.
        """

    @abc.abstractmethod
    def get_bindings(self):
        """
        Returns an iterator over SparqlResultBinding objects.

        May only be called once, and may raise TypeError if the stream
        doesn't represent a resultset.
        """

    @abc.abstractmethod
    def get_boolean(self):
        """
        Returns a boolean result for a SPARQL query.

        May be called more than once, and may raise TypeError if the stream
        doesn't represent a boolean result.
        """

    @abc.abstractmethod
    def get_triples(self):
        """
        Returns an iterator over the triples in a stream.

        May only be called once, and may raise TypeError if the stream doesn't
        represent triples.
        """

    def read(self, num=None):
        self.mode = 'stream'
        return self._stream.read(num)

    def readline(self):
        self.mode = 'stream'
        return self._stream.readline()

    def __iter__(self):
        self.mode = 'stream'
        return iter(self._stream)

    def get(self):
        """
        Returns an in-memory object representing the stream.

        You will either get a SparqlResultsList, a bool, or a ConjunctiveGraph.
        """
        if self._cached_get is None:
            sparql_results_type = self.get_sparql_results_type()
            if sparql_results_type == 'resultset':
                self._cached_get = SparqlResultList(self.get_fields(), self.get_bindings())
            elif sparql_results_type == 'boolean':
                self._cached_get = self.get_boolean()
            elif sparql_results_type == 'graph':
                graph = rdflib.ConjunctiveGraph()
                for prefix, namespace_uri in NS.items():
                    graph.namespace_manager.bind(prefix, namespace_uri)
                graph += self.get_triples()
                self._cached_get = graph
            else:
                raise AssertionError("Unexpected results type: {0}".format(sparql_results_type))
            for name in ('query', 'duration'):
                if hasattr(self, name):
                    setattr(self._cached_get, name, getattr(self, name))
        return self._cached_get

class StreamingSerializer(object, metaclass=abc.ABCMeta):
    def __init__(self, results):
        self._results = results

    def __iter__(self):
        results = self._results

        if isinstance(results, StreamingParser) and results.media_type == self.media_type:
            statsd.incr('humfrey.streaming.pass-through.yes')
            return iter(results)
        else:
            statsd.incr('humfrey.streaming.pass-through.no')

        sparql_results_type, fields, bindings, boolean, triples = None, None, None, None, None

        if isinstance(results, bool):
            sparql_results_type, boolean = 'boolean', results
        elif isinstance(results, SparqlResultList):
            sparql_results_type, fields, bindings = 'resultset', results.fields, results
        elif isinstance(results, StreamingParser):
            sparql_results_type = results.get_sparql_results_type()
            if sparql_results_type == 'resultset':
                fields, bindings = results.get_fields(), results.get_bindings()
                boolean, triples = None, None
            elif sparql_results_type == 'boolean':
                boolean = results.get_boolean()
                fields, bindings, triples = None, None, None
            elif sparql_results_type == 'graph':
                triples = results.get_triples()
                fields, bindings, boolean = None, None, None
        # Assume iterable-ish things are graphs / lists of triples
        elif isinstance(results, (list, types.GeneratorType, rdflib.ConjunctiveGraph)):
            sparql_results_type, triples = 'graph', results
        elif hasattr(results, '__iter__'):
            sparql_results_type, triples = 'graph', results
        else:
            raise TypeError("{0} object cannot be serialized".format(type(results)))

        if sparql_results_type not in self.supported_results_types:
            raise TypeError("Unexpected results type: {0}".format(sparql_results_type))

        return self._iter(sparql_results_type, fields, bindings, boolean, triples)

    @abc.abstractmethod
    def _iter(self, sparql_results_type, fields, bindings, boolean, triples):
        pass

    @abc.abstractproperty
    def supported_results_types(self):
        pass

    def serialize(self, stream):
        for line in self:
            stream.write(line)
