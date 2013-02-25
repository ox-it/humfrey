"""
Contains wrappers around rdflib parsers and serializers.
"""

import abc
import Queue
import sys
import threading
from xml.sax.saxutils import prepare_input_source

from rdflib import ConjunctiveGraph, Graph, plugin

try:  # rdflib 3.x
    from rdflib.parser import Parser
    from rdflib.serializer import Serializer
except ImportError:  # rdflib 2.4.x
    from rdflib.syntax.parsers import Parser
    from rdflib.syntax.serializers import Serializer

from humfrey.utils.namespaces import NS

from .base import StreamingParser, StreamingSerializer
from .encoding import coerce_triple_iris

class _QueueGraph(Graph):
    def __init__(self, queue, *args, **kwargs):
        self._queue = queue
        super(_QueueGraph, self).__init__(*args, **kwargs)

    def add(self, triple):
        self._queue.put(('triple', triple))

class _QueueStream(object):
    def __init__(self, queue):
        self._queue = queue

    def write(self, data):
        self._queue.put(('data', data))

class RDFLibParser(StreamingParser):
    format_type = 'graph'

    @abc.abstractproperty
    def rdflib_parser(self):
        pass

    @abc.abstractproperty
    def parser_args(self):
        pass
    @abc.abstractproperty
    def parser_kwargs(self):
        pass

    def _parse_to_queue(self, stream, queue):
        parser = self.rdflib_parser()
        store = _QueueGraph(queue)
        source = prepare_input_source(stream)
        try:
            parser.parse(source, store,
                         *self.parser_args, **self.parser_kwargs)
        except:
            queue.put(('exception', sys.exc_info()))
        else:
            queue.put(('sentinel', None)) # Sentinel

    def get_sparql_results_type(self):
        self.mode = 'parse'
        return 'graph'

    def get_fields(self):
        raise TypeError("This is a graph parser")

    def get_bindings(self):
        raise TypeError("This is a graph parser")

    def get_boolean(self):
        raise TypeError("This is a graph parser")

    def _get_triples(self):
        if getattr(self, '_get_triples_called', False):
            raise AssertionError("Can only call get_triples once")
        self._get_triples_called = True
        self.mode = 'parse'
        queue = Queue.Queue()
        parser_thread = threading.Thread(target=self._parse_to_queue,
                                         args=(self._stream, queue))
        parser_thread.start()

        while True:
            type, value = queue.get()
            if type == 'triple':
                yield value
            elif type == 'sentinel':
                break
            elif type == 'exception':
                raise value[0], value[1], value[2]

        parser_thread.join()

    def get_triples(self):
        return coerce_triple_iris(self._get_triples())

class RDFLibSerializer(StreamingSerializer):
    supported_results_types = ('graph',)
    format_type = 'graph'

    def _iter(self, sparql_results_type, fields, bindings, boolean, triples):
        queue = Queue.Queue()
        graph = ConjunctiveGraph()
        for prefix, namespace_uri in NS.iteritems():
            graph.namespace_manager.bind(prefix, namespace_uri)
        graph += list(triples)
        serializer_thread = threading.Thread(target=self._serialize_to_queue,
                                             args=(graph, queue))
        serializer_thread.start()

        while True:
            type, value = queue.get()
            if type == 'data':
                yield value
            elif type == 'sentinel':
                break
            elif type == 'exception':
                raise value[0], value[1], value[2]

        serializer_thread.join()

    def _serialize_to_queue(self, graph, queue):
        serializer = self.rdflib_serializer(graph)
        stream = _QueueStream(queue)
        try:
            serializer.serialize(stream)
        except:
            queue.put(('exception', sys.exc_info()))
        else:
            queue.put(('sentinel', None)) # Sentinel

def get_rdflib_parser(name, media_type, plugin_name,
                      parser_args=(), parser_kwargs={}):
    rdflib_parser = plugin.get(plugin_name, Parser)
    return type(name,
                (RDFLibParser,),
                {'media_type': media_type,
                 'rdflib_parser': rdflib_parser,
                 'parser_args': parser_args,
                 'parser_kwargs': parser_kwargs})

def get_rdflib_serializer(name, media_type, plugin_name):
    rdflib_serializer = plugin.get(plugin_name, Serializer)
    return type(name,
                (RDFLibSerializer,),
                {'media_type': media_type,
                 'rdflib_serializer': rdflib_serializer})
