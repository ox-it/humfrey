from xml.sax.saxutils import escape
try:
    import json
except ImportError:
    import simplejson as json

import rdflib

from django.http import HttpResponse

from django_conneg.decorators import renderer

from humfrey.utils.views import EndpointView
from humfrey.utils.sparql import SparqlResultList, SparqlResultBool

# Register the RDF/JSON and JSON-LD serializer plugins
from rdflib import plugin
from rdflib.serializer import Serializer
plugin.register("rdf-json", Serializer, 'rdfextras.serializers.rdfjson', 'RdfJsonSerializer')
plugin.register("json-ld", Serializer, 'rdfextras.serializers.jsonld', 'JsonLDSerializer')
del plugin, Serializer

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
            for format, mimetype, method, name in serializations:
                dict['render_%s' % format] = mcs.get_rdf_renderer(format, mimetype, method, name)

        return super(_RDFViewMetaclass, mcs).__new__(mcs, name, bases, dict)

class RDFView(EndpointView):
    __metaclass__ = _RDFViewMetaclass

    RDF_SERIALIZATIONS = (
        ('rdf', 'application/rdf+xml', 'pretty-xml', 'RDF/XML'),
        ('nt', 'text/plain', 'nt', 'N-Triples'),
        ('ttl', 'text/turtle', 'turtle', 'Turtle'),
        ('n3', 'text/n3', 'n3', 'Notation3'),
        ('rdfjson', 'application/rdf+json', 'rdf-json', 'RDF/JSON'),
        ('jsonld', 'application/ld+json', 'json-ld', 'JSON-LD'),
    )

class ResultSetView(EndpointView):
    def _spool_srx_boolean(self, result):
        yield '<?xml version="1.0"?>\n'
        yield '<sparql xmlns="http://www.w3.org/2005/sparql-results#">\n'
        yield '  <head/>\n'
        yield '  <boolean>%s</boolean>\n' % ('true' if result else 'false')
        yield '</sparql>\n'

    def _spool_srx_resultset(self, results):
        yield '<?xml version="1.0"?>\n'
        yield '<sparql xmlns="http://www.w3.org/2005/sparql-results#">\n'
        yield '  <head>\n'
        for binding in results.fields:
            yield '    <variable name="%s"/>\n' % escape(binding)
        yield '  </head>\n'
        yield '  <results>\n'
        for result in results:
            yield '    <result>\n'
            for field in result._fields:
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
        yield '</sparql>\n'

    def _spool_srj_boolean(self, result):
        yield '{\n'
        yield '  "head": {},\n'
        yield '  "boolean": %s\n' % ('true' if result else 'false')
        yield '}\n'

    def _spool_srj_resultset(self, results):
        dumps = json.dumps
        yield '{\n'
        yield '  "head": {\n'
        yield '    "vars": [ %s ]\n' % ', '.join(dumps(v) for v in results.fields)
        yield '  },\n'
        yield '  "results": {\n'
        yield '    "bindings": [\n'
        for i, result in enumerate(results):
            yield '      {' if i == 0 else ',\n      {'
            j = 0
            for name, value in result._asdict().iteritems():
                if value is None:
                    continue
                yield ',\n' if j > 0 else '\n'
                yield '        %s: { "type": ' % dumps(name.encode('utf8'))
                if isinstance(value, rdflib.URIRef):
                    yield dumps('uri')
                elif isinstance(value, rdflib.BNode):
                    yield dumps('bnode')
                elif value.datatype:
                    yield '%s, "datatype": %s' % (dumps('typed-literal'), dumps(value.datatype.encode('utf8')))
                elif value.language:
                    yield '%s, "xml:lang": %s' % (dumps('literal'), dumps(value.language.encode('utf8')))
                else:
                    yield dumps('literal')
                yield ', "value": %s }' % dumps(value.encode('utf8'))
                j += 1
            yield '\n      }'
        yield '\n    ]\n'
        yield '  }\n'
        yield '}\n'

    def _spool_csv_boolean(self, result):
        yield '%s\n' % ('true' if result else 'false')

    def _spool_csv_resultset(self, results):
        def quote(value):
            if value is None:
                return ''
            value = value.replace('"', '""')
            if any(bad_char in value for bad_char in '\n" ,'):
                value = '"%s"' % value
            return value
        for result in results:
            yield ",".join(quote(value) for value in result)
            yield '\n'

    def render_resultset(self, request, context, spool_boolean, spool_resultset, mimetype):
        if isinstance(context.get('result'), SparqlResultBool):
            spool = spool_boolean(context['result'])
        elif isinstance(context.get('results'), SparqlResultList):
            spool = spool_resultset(context['results'])
        else:
            return NotImplemented
        return HttpResponse(spool, mimetype=mimetype)

    @renderer(format='srx', mimetypes=('application/sparql-results+xml',), name='SPARQL Results XML')
    def render_srx(self, request, context, template_name):
        return self.render_resultset(request, context,
                                     self._spool_srx_boolean,
                                     self._spool_srx_resultset,
                                     'application/sparql-results+xml')

    @renderer(format='srj', mimetypes=('application/sparql-results+json',), name='SPARQL Results JSON')
    def render_srj(self, request, context, template_name):
        return self.render_resultset(request, context,
                                     self._spool_srj_boolean,
                                     self._spool_srj_resultset,
                                     'application/sparql-results+json')

    @renderer(format='csv', mimetypes=('text/csv',), name='CSV')
    def render_csv(self, request, context, template_name):
        return self.render_resultset(request, context,
                                     self._spool_csv_boolean,
                                     self._spool_csv_resultset,
                                     'text/csv;charset=UTF-8')
