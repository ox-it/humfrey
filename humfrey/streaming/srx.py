import logging
import Queue
import threading
import xml.sax
from xml.sax.saxutils import escape

import rdflib

from humfrey.sparql.results import Result, SparqlResultSet, SparqlResultList, SparqlResultBool

logger = logging.getLogger(__name__)

class SRXSource(object):

    class SRXContentHandler(xml.sax.ContentHandler):
        feature_namespaces = True

        def __init__(self, queue):
            self.queue = queue
            self.fields = []
            self.result = None
            self.srx_ns = 'http://www.w3.org/2005/sparql-results#'
            self.xml_ns = 'http://www.w3.org/XML/1998/namespace'
            self.content = []

        def startDocument(self):
            pass
        def startElementNS(self, name, qname, attrs):
            if name == (self.srx_ns, 'results'):
                self.queue.put('resultset')
                self.queue.put(tuple(self.fields))
            elif name == (self.srx_ns, 'boolean'):
                self.queue.put('boolean')
            elif name == (self.srx_ns, 'variable'):
                self.fields.append(attrs[(None, 'name')])
            elif name == (self.srx_ns, 'result'):
                self.result = {}
            elif name == (self.srx_ns, 'binding'):
                self.binding_name = attrs[(None, 'name')]
                self.binding = None
            elif name == (self.srx_ns, 'literal'):
                # rdflib will turn the datatype into a URIRef for us
                self.literal_kwargs = {'lang': attrs.get((self.xml_ns, 'lang')),
                                       'datatype': attrs.get((None, 'datatype'))}

            self.content = []

        def endElementNS(self, name, qname):
            content = ''.join(self.content) if self.content else None
            if name == (self.srx_ns, 'result'):
                self.queue.put(self.result)
                self.result = None
            elif name == (self.srx_ns, 'binding'):
                self.result[self.binding_name] = self.binding
                self.binding_name, self.binding = None, None
            elif name == (self.srx_ns, 'boolean'):
                self.queue.put(self.content == 'true')
            elif name == (self.srx_ns, 'uri'):
                self.binding = rdflib.URIRef(content)
            elif name == (self.srx_ns, 'bnode'):
                self.binding = rdflib.BNode(content)
            elif name == (self.srx_ns, 'literal'):
                self.binding = rdflib.Literal(content, **self.literal_kwargs)
            content = None

        def characters(self, content):
            self.content.append(content)

    def __init__(self, stream, encoding='utf-8'):
        self.stream = stream
        self.encoding = encoding

        self._finished = False

        self._queue = Queue.Queue(maxsize=128)
        self._thread = threading.Thread(target=self._parse)
        self._thread.start()

        self.type = self._queue.get()
        if self.type == 'resultset':
            self.fields = self._queue.get()
            self.__class__ = SRXSourceResultSet
        elif self.type == 'boolean':
            self.fields = self._queue.get()
            self.__class__ = SRXSourceResultBool

    def _parse(self):
        handler = self.SRXContentHandler(self._queue)
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_namespaces, True)
        parser.setContentHandler(handler)
        try:
            parser.parse(self.stream)
        except Exception:
            logger.exception("Failed to parse stream")
        finally:
            self._queue.put(None)

    def __iter__(self):
        while not self._finished:
            value = self._queue.get()
            if value is None:
                self._finished = True
                break
            if isinstance(value, bool):
                yield value
            else:
                yield Result(self.fields, value)
        self._thread.join()

    def get(self):
        if self.type == 'resultset':
            return SparqlResultList(self.fields, self)
        else:
            return self.__nonzero__()
    
    def __nonzero__(self):
        if self.type != 'boolean':
            raise TypeError("This isn't a boolean result")
        try:
            return self._bool
        except AttributeError:
            self._bool = self._next()
            return self._bool

class SRXSourceResultSet(SparqlResultSet, SRXSource):
    pass
class SRXSourceResultBool(SRXSource, SparqlResultBool):
    pass


class SRXSerializer(object):
    def __init__(self, results):
        self.results = results

    def __iter__(self):
        results = self.results

        yield '<?xml version="1.0"?>\n'
        yield '<sparql xmlns="http://www.w3.org/2005/sparql-results#">\n'

        if getattr(self.results, 'fields', None):
            yield '  <head>\n'
            for binding in results.fields:
                yield '    <variable name="%s"/>\n' % escape(binding)
            yield '  </head>\n'

            yield '  <results>\n'
            for result in results:
                yield '    <result>\n'
                for field in result.fields:
                    value = getattr(result, field)
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
            yield '  <boolean>%s</boolean>\n' % ('true' if results else 'false')
        
        yield '</sparql>\n'

    def serialize(self, stream):
        for line in self:
            stream.write(line)
