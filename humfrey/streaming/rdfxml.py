import re
from xml.sax.saxutils import quoteattr, escape

try: # rdflib 3.0
    from rdflib.plugins.parsers.rdfxml import RDFXMLParser as RDFXMLParser_
except ImportError: # rdflib 2.4.x
    from rdflib.syntax.parsers.RDFXMLParser import RDFXMLParser as RDFXMLParser_
from rdflib import Graph, URIRef, Literal, BNode

from humfrey.utils.namespaces import NS

from .base import StreamingSerializer


class RDFXMLSerializer(StreamingSerializer):
    localpart = re.compile(r'[A-Za-z_][A-Za-z_\d\-]+$')
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
                    yield '  <rdf:Description rdf:about={}>\n'.format(quoteattr(s))
                elif isinstance(s, BNode):
                    yield '  <rdf:Description rdf:nodeID={}>\n'.format(quoteattr(s))
                else:
                    raise AssertionError("Unexpected subject term: %r (%r)" % (type(s), s))

            if not isinstance(p, URIRef):
                raise AssertionError("Unexpected predicate term: %r (%r)" % (type(p), p))
            for prefix, uri in namespaces:
                if p.startswith(uri) and self.localpart.match(p[len(uri):]):
                    tag_name = '{}:{}'.format(prefix, p[len(uri):])
                    yield '    <{}'.format(tag_name)
                    break
            else:
                match = self.localpart.search(p)
                tag_name = p[match.start():]
                yield '    <{} xmlns={}'.format(tag_name, quoteattr(p[:match.start()]))

            if isinstance(o, Literal):
                if o.language:
                    yield ' xml:lang={}'.format(quoteattr(o.language))
                if o.datatype:
                    yield ' rdf:datatype={}'.format(quoteattr(o.datatype))
                yield '>{}</{}>\n'.format(escape(o), tag_name)
            elif isinstance(o, BNode):
                yield ' rdf:nodeID={}/>\n'.format(quoteattr(o))
            elif isinstance(o, URIRef):
                yield ' rdf:resource={}/>\n'.format(quoteattr(o))
            else:
                raise AssertionError("Unexpected object term: %r (%r)" % (type(o), o))

        if last_subject is not None:
            yield '  </rdf:Description>\n'
        yield '</rdf:RDF>\n'
