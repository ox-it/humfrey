import Queue
import re
import sys
import threading
from xml.sax.saxutils import quoteattr, escape

try: # rdflib 3.0
    from rdflib.plugins.parsers.rdfxml import RDFXMLParser as RDFXMLParser_
except ImportError: # rdflib 2.4.x
    from rdflib.syntax.parsers.RDFXMLParser import RDFXMLParser as RDFXMLParser_
from rdflib import Graph, URIRef, Literal, BNode

from humfrey.utils.namespaces import NS

from .base import StreamingParser, StreamingSerializer
from .wrapper import get_rdflib_parser

class RDFXMLSerializer(StreamingSerializer):
    localpart = re.compile(ur'[A-Za-z_][A-Za-z_\d\-]+$')
    supported_results_types = ('graph',)
    media_type = 'application/rdf+xml'
    format_type = 'graph'

    def _iter(self, sparql_results_type, fields, bindings, boolean, triples):
        namespaces = sorted((NS).items())
        last_subject = None

        # XML declaration, root element and namespaces
        yield '<?xml version="1.0" encoding="utf-8"?>\n'
        yield '<rdf:RDF'
        for prefix, uri in namespaces:
            yield '\n    xmlns:%s=%s' % (prefix, quoteattr(uri))
        yield '>\n'

        # Triples
        for s, p, o in triples:
            if s != last_subject:
                if last_subject is not None:
                    yield '  </rdf:Description>\n'
                last_subject = s
                if isinstance(s, URIRef):
                    yield '  <rdf:Description rdf:about=%s>\n' % quoteattr(s).encode('utf-8')
                elif isinstance(s, BNode):
                    yield '  <rdf:Description rdf:nodeID=%s>\n' % quoteattr(s).encode('utf-8')
                else:
                    raise AssertionError("Unexpected subject term: %r (%r)" % (type(s), s))

            if not isinstance(p, URIRef):
                raise AssertionError("Unexpected predicate term: %r (%r)" % (type(p), p))
            for prefix, uri in namespaces:
                if p.startswith(uri) and self.localpart.match(p[len(uri):]):
                    tag_name = '%s:%s' % (prefix, p[len(uri):])
                    yield '    <%s' % tag_name.encode('utf-8')
                    break
            else:
                match = self.localpart.search(p)
                tag_name = p[match.start():]
                yield '    <%s xmlns=%s' % (tag_name.encode('utf-8'),
                                             quoteattr(p[:match.start()]).encode('utf-8'))

            if isinstance(o, Literal):
                if o.language:
                    yield ' xml:lang=%s' % quoteattr(o.language).encode('utf-8')
                if o.datatype:
                    yield ' rdf:datatype=%s' % quoteattr(o.datatype).encode('utf-8')
                yield '>%s</%s>\n' % (escape(o).encode('utf-8'), tag_name.encode('utf-8'))
            elif isinstance(o, BNode):
                yield ' rdf:nodeID=%s/>\n' % quoteattr(o).encode('utf-8')
            elif isinstance(o, URIRef):
                yield ' rdf:resource=%s/>\n' % quoteattr(o).encode('utf-8')
            else:
                raise AssertionError("Unexpected object term: %r (%r)" % (type(o), o))

        if last_subject is not None:
            yield '  </rdf:Description>\n'
        yield '</rdf:RDF>\n'
