import logging
import queue
import threading
from xml.sax.saxutils import escape
from xml.parsers import expat

import rdflib

from humfrey.sparql.results import Result
from .base import StreamingParser, StreamingSerializer

logger = logging.getLogger(__name__)

class SRXParser(StreamingParser):
    class SRXContentHandler(object):
        def __init__(self, queue):
            self.queue = queue
            self.fields = []
            self.result = None
            self.srx_ns = 'http://www.w3.org/2005/sparql-results#'
            self.xml_ns = 'http://www.w3.org/XML/1998/namespace'
            self.content = []

        def start_element(self, name, attrs):
            if name == (self.srx_ns + ' results'):
                self.queue.put('resultset')
                self.queue.put(tuple(self.fields))
            elif name == (self.srx_ns + ' boolean'):
                self.queue.put('boolean')
            elif name == (self.srx_ns + ' variable'):
                self.fields.append(attrs['name'])
            elif name == (self.srx_ns + ' result'):
                self.result = {}
            elif name == (self.srx_ns + ' binding'):
                self.binding_name = attrs['name']
            elif name == (self.srx_ns + ' literal'):
                # rdflib will turn the datatype into a URIRef for us
                self.literal_kwargs = {'lang': attrs.get(self.xml_ns + ' lang'),
                                       'datatype': attrs.get('datatype')}

            self.content = []

        def end_element(self, name):
            content = ''.join(self.content)
            if name == (self.srx_ns + ' result'):
                self.queue.put(self.result)
                self.result = None
            elif name == (self.srx_ns + ' binding'):
                self.result[self.binding_name] = self.binding
                self.binding_name, self.binding = None, None
            elif name == (self.srx_ns + ' boolean'):
                self.queue.put(content == 'true')
            elif name == (self.srx_ns + ' uri'):
                self.binding = rdflib.URIRef(content)
            elif name == (self.srx_ns + ' bnode'):
                self.binding = rdflib.BNode(content)
            elif name == (self.srx_ns + ' literal'):
                self.binding = rdflib.Literal(content, **self.literal_kwargs)

        def char_data(self, data):
            self.content.append(data)

    media_type = 'application/sparql-results+xml'
    format_type = 'sparql-results'

    def get_sparql_results_type(self):
        if hasattr(self, '_sparql_results_type'):
            return self._sparql_results_type
        self.mode = 'parse'

        self._finished = False

        self._queue = queue.Queue(maxsize=128)
        self._thread = threading.Thread(target=self._parse)
        self._thread.start()

        self._sparql_results_type = self._queue.get()
        if self._sparql_results_type == 'resultset':
            self._fields = self._queue.get()
        elif self._sparql_results_type == 'boolean':
            self._boolean = self._queue.get()
        else:
            raise AssertionError("Unexpected result type: {0}".format(self._sparql_results_type))
        return self._sparql_results_type

    def _parse(self):
        handler = self.SRXContentHandler(self._queue)
        parser = expat.ParserCreate(namespace_separator=' ')
        parser.StartElementHandler = handler.start_element
        parser.EndElementHandler = handler.end_element
        parser.CharacterDataHandler = handler.char_data

        try:
            parser.ParseFile(self._stream)
        except Exception:
            logger.exception("Failed to parse stream")
        finally:
            self._queue.put(None)

    def get_fields(self):
        if self.get_sparql_results_type() != 'resultset':
            raise TypeError("This isn't a resultset.")
        return self._fields

    def get_bindings(self):
        fields = self.get_fields()
        if self._finished:
            raise AssertionError("This method can only be called once.")
        while not self._finished:
            value = self._queue.get()
            if value is None:
                self._finished = True
            else:
                yield Result(fields, value)
        self._thread.join()

    def get_boolean(self):
        if self.get_sparql_results_type() != 'boolean':
            raise TypeError("This isn't a boolean result.")
        return self._boolean

    def get_triples(self):
        raise TypeError("This isn't a graph result.")

class SRXSerializer(StreamingSerializer):
    media_type = 'application/sparql-results+xml'
    supported_results_types = ('resultset', 'boolean')
    format_type = 'sparql-results'

    def _iter(self, sparql_results_type, fields, bindings, boolean, triples):
        if sparql_results_type not in ('resultset', 'boolean'):
            raise TypeError("Unexpected results type: {0}".format(sparql_results_type))

        yield '<?xml version="1.0"?>\n'
        yield '<sparql xmlns="http://www.w3.org/2005/sparql-results#">\n'

        if fields is not None:
            yield '  <head>\n'
            for field in fields:
                yield '    <variable name="%s"/>\n' % escape(field)
            yield '  </head>\n'

            yield '  <results>\n'
            for binding in bindings:
                yield '    <result>\n'
                for field in fields:
                    value = getattr(binding, field)
                    if value is None:
                        continue
                    yield '      <binding name="%s">\n' % escape(field)
                    yield ' ' * 8
                    if isinstance(value, rdflib.URIRef):
                        yield '<uri>%s</uri>' % escape(value).encode('utf-8')
                    elif isinstance(value, rdflib.BNode):
                        yield '<bnode>%s</bnode>' % escape(value).encode('utf-8')
                    elif isinstance(value, rdflib.Literal):
                        yield '<literal'
                        if value.datatype:
                            yield ' datatype="%s"' % escape(value.datatype).encode('utf-8')
                        if value.language:
                            yield ' xml:lang="%s"' % escape(value.language).encode('utf-8')
                        yield '>%s</literal>' % escape(value).encode('utf-8')
                    yield '\n      </binding>\n'
                yield '    </result>\n'
            yield '  </results>\n'

        else:
            yield '  <head/>\n'
            yield '  <boolean>%s</boolean>\n' % ('true' if boolean else 'false')

        yield '</sparql>\n'
