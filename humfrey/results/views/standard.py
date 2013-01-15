from __future__ import absolute_import

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import functools
import imp
from xml.sax.saxutils import escape
try:
    import simplejson as json
except ImportError:
    import json

import rdflib
import rdflib.plugin
try: # This moved during the transition from rdflib 2.4 to rdflib 3.0.
    from rdflib.serializer import Serializer # 3.0
except ImportError:
    from rdflib.syntax.serializers import Serializer # 2.4

from django.http import HttpResponse

from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView

from humfrey.sparql.results import SparqlResultSet, SparqlResultBool
from humfrey.streaming import srx
from humfrey.utils.statsd import statsd

# Register the RDF/JSON and JSON-LD serializer plugins if available
try:
    imp.find_module('rdfextras.serializers.rdfjson')
    rdflib.plugin.register("rdf-json", Serializer, 'rdfextras.serializers.rdfjson', 'RdfJsonSerializer')
    with_rdfjson_serializer = True
except ImportError:
    with_rdfjson_serializer = False
try:
    imp.find_module('rdfextras.serializers.jsonld')
    rdflib.plugin.register("rdf-json", Serializer, 'rdfextras.serializers.jsonld', 'JsonLDSerializer')
    with_jsonld_serializer = True
except ImportError:
    with_jsonld_serializer = False

class _RDFViewMetaclass(type):
    @classmethod
    def get_rdf_renderer(mcs, format, mimetype, method, name):
        @renderer(format=format, mimetypes=(mimetype,), name=name)
        def render(self, request, context, template_name):
            graph = context.get('graph')
            if not isinstance(graph, rdflib.ConjunctiveGraph):
                return NotImplemented
            return HttpResponse(graph.serialize(format=method), mimetype=mimetype)
        render.__name__ = 'render_%s' % format
        return render

    def __new__(mcs, name, bases, dict):
        if 'RDF_SERIALIZATIONS' in dict:
            serializations = dict.pop('RDF_SERIALIZATIONS')
            for format, mimetype, method, renderer_name in serializations:
                dict['render_%s' % format] = mcs.get_rdf_renderer(format, mimetype, method, renderer_name)

        return super(_RDFViewMetaclass, mcs).__new__(mcs, name, bases, dict)

class RDFView(ContentNegotiatedView):
    __metaclass__ = _RDFViewMetaclass

    RDF_SERIALIZATIONS = (
        ('rdf', 'application/rdf+xml', 'pretty-xml', 'RDF/XML'),
        ('nt', 'text/plain', 'nt', 'N-Triples'),
        ('ttl', 'text/turtle', 'turtle', 'Turtle'),
        ('n3', 'text/n3', 'n3', 'Notation3'),
    )
    if with_rdfjson_serializer:
        RDF_SERIALIZATIONS += (('rdfjson', 'application/rdf+json', 'rdf-json', 'RDF/JSON'),)
    if with_jsonld_serializer:
        RDF_SERIALIZATIONS += (('jsonld', 'application/ld+json', 'json-ld', 'JSON-LD'),)


class ResultSetView(ContentNegotiatedView):
    def _spool_srj_boolean(self, result, callback=None):
        with statsd.timer('humfrey.serialization.srj-boolean'):
            if callback:
                yield callback
                yield '('
            yield '{\n'
            yield '  "head": {},\n'
            yield '  "boolean": %s\n' % ('true' if result else 'false')
            yield '}'
            if callback:
                yield ')'
            yield '\n'

    @statsd.timer('humfrey.serialization.srj-boolean')
    def _spool_srj_resultset(self, results, callback=None):
        with statsd.timer('humfrey.serialization.srj-resultset'):
            buffer = StringIO()
            dumps = json.dumps
            URI, BNODE, LITERAL, TYPED_LITERAL = map(dumps, ['uri', 'bnode', 'literal', 'typed-literal'])

            if callback:
                buffer.write(callback)
                buffer.write('(')
            buffer.write('{\n')
            buffer.write('  "head": {\n')
            buffer.write('    "vars": [ %s ]\n' % ', '.join(dumps(v) for v in results.fields))
            buffer.write('  },\n')
            buffer.write('  "results": {\n')
            buffer.write('    "bindings": [\n')
            for i, result in enumerate(results):
                buffer.write('      {' if i == 0 else ',\n      {')
                j = 0
                for name, value in result._asdict().iteritems():
                    if value is None:
                        continue
                    buffer.write(',\n' if j > 0 else '\n')
                    buffer.write('        %s: { "type": ' % dumps(name.encode('utf8')))
                    if isinstance(value, rdflib.URIRef):
                        buffer.write(URI)
                    elif isinstance(value, rdflib.BNode):
                        buffer.write(BNODE)
                    elif value.datatype:
                        buffer.write('%s, "datatype": %s' % (TYPED_LITERAL, dumps(value.datatype.encode('utf8'))))
                    elif value.language:
                        buffer.write('%s, "xml:lang": %s' % (LITERAL, dumps(value.language.encode('utf8'))))
                    else:
                        buffer.write(LITERAL)
                    buffer.write(', "value": %s }' % dumps(value.encode('utf8')))

                    if buffer.tell() > 65000: # Almost 64k
                        yield buffer.getvalue()
                        buffer.seek(0)
                        buffer.truncate()

                    j += 1
                buffer.write('\n      }')
            buffer.write('\n    ]\n')
            buffer.write('  }\n')
            buffer.write('}')
            if callback:
                buffer.write(')')
            buffer.write('\n')
            yield buffer.getvalue()
            buffer.close()

    def _spool_csv_boolean(self, result):
        with statsd.timer('humfrey.serialization.csv-boolean'):
            yield '%s\n' % ('true' if result else 'false')

    def _spool_csv_resultset(self, results, include_header=True):
        with statsd.timer('humfrey.serialization.csv-resultset'):
            def quote(value):
                if value is None:
                    return ''
                value = value.replace('"', '""')
                if any(bad_char in value for bad_char in '\n" ,'):
                    value = '"%s"' % value
                return value
            if include_header:
                yield ','.join(quote(field) for field in results.fields)
                yield '\n'
            for result in results:
                yield ",".join(quote(value) for value in result)
                yield '\n'

    def render_resultset(self, request, context, spool_boolean, spool_resultset, mimetype):
        if isinstance(context.get('result'), SparqlResultBool):
            spool = spool_boolean(context['result'])
        elif isinstance(context.get('results'), SparqlResultSet):
            spool = spool_resultset(context['results'])
        else:
            return NotImplemented
        return HttpResponse(spool, mimetype=mimetype)

    @renderer(format='srx', mimetypes=('application/sparql-results+xml',), name='SPARQL Results XML')
    def render_srx(self, request, context, template_name):
        return self.render_resultset(request, context,
                                     srx.SRXSerializer, srx.SRXSerializer,
                                     'application/sparql-results+xml')

    @renderer(format='srj', mimetypes=('application/sparql-results+json',), name='SPARQL Results JSON')
    def render_srj(self, request, context, template_name):
        callback = request.GET.get('callback')

        return self.render_resultset(request, context,
                                     functools.partial(self._spool_srj_boolean, callback=callback),
                                     functools.partial(self._spool_srj_resultset, callback=callback),
                                     'application/javascript' if callback else 'application/sparql-results+json')

    @renderer(format='csv', mimetypes=('text/csv',), name='CSV')
    def render_csv(self, request, context, template_name):
        return self.render_resultset(request, context,
                                     self._spool_csv_boolean,
                                     self._spool_csv_resultset,
                                     'text/csv;charset=UTF-8')
