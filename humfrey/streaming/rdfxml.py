import Queue
import re
import threading
from xml.sax.saxutils import quoteattr, escape

try: # rdflib 3.0
    from rdflib.plugins.parsers.rdfxml import RDFXMLParser
except ImportError: # rdflib 2.4.x
    from rdflib.syntax.parsers.RDFXMLParser import RDFXMLParser
from rdflib import Graph, URIRef, Literal, BNode

#from rdflib.plugins.memory.IOMemory

from humfrey.utils.namespaces import NS

class QueueGraph(Graph):
    def __init__(self, queue, *args, **kwargs):
        self.queue = queue
        super(QueueGraph, self).__init__(*args, **kwargs)

    def add(self, triple):
        self.queue.put(triple)

class RDFXMLSource(object):
    def __init__(self, f):
        self.file = f
        self.queue = Queue.Queue(maxsize=10)

    def parser(self, file, queue):
        parser = RDFXMLParser()
        store = QueueGraph(queue)
        try:
            parser.parse(file, store)
        finally:
            queue.put(None) # Sentinel

    def __iter__(self):
        parser_thread = threading.Thread(target=self.parser,
                                         args=(self.file, self.queue))
        parser_thread.start()

        queue = self.queue

        while True:
            triple = queue.get()
            if triple is None:
                break
            yield triple

        parser_thread.join()

class RDFXMLSink(object):
    localpart = re.compile(ur'[A-Za-z_][A-Za-z_\d\-]+$')

    def __init__(self, triples, namespaces=None, encoding='utf-8'):
        self.triples = triples
        self.namespaces = sorted((namespaces or NS).items())
        self.encoding = encoding
        self.last_subject = None

    def serialize(self, out):
        write = lambda s: out.write(s.encode(self.encoding))
        write(u'<?xml version="1.0" encoding=%s?>\n' % quoteattr(self.encoding))
        write(u'<rdf:RDF')
        for prefix, uri in self.namespaces:
            write(u'\n    xmlns:%s=%s' % (prefix, quoteattr(uri)))
        write(u'>\n')
        for triple in self.triples:
            self.triple(write, triple)
        if self.last_subject:
            write(u'  </rdf:Description>\n')
        write(u'</rdf:RDF>\n')

    def triple(self, write, (s, p, o)):
        if s != self.last_subject:
            if self.last_subject:
                write(u'  </rdf:Description>\n')
            self.last_subject = s
            if isinstance(s, URIRef):
                write(u'  <rdf:Description rdf:about=%s>\n' % quoteattr(s))
            else:
                write(u'  <rdf:Description rdf:nodeID=%s>\n' % quoteattr(s))
        for prefix, uri in self.namespaces:
            if p.startswith(uri) and self.localpart.match(p[len(uri):]):
                tag_name = '%s:%s' % (prefix, p[len(uri):])
                write(u'    <%s' % tag_name)
                break
        else:
            match = self.localpart.search(p)
            tag_name = p[match.start():]
            write(u'    <%s xmlns=%s' % (tag_name, quoteattr(p[:match.start()])))

        if isinstance(o, Literal):
            if o.language:
                write(u' xml:lang=%s' % quoteattr(o.language))
            if o.datatype:
                write(u' rdf:datatype=%s' % quoteattr(o.datatype))
            write('>%s</%s>\n' % (escape(o), tag_name))
        elif isinstance(o, BNode):
            write(u' rdf:nodeID=%s/>\n' % quoteattr(o))
        else:
            write(u' rdf:resource=%s/>\n' % quoteattr(o))

