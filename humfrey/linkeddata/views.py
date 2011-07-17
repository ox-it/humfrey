import base64
import hashlib
import pickle
from xml.sax.saxutils import escape

import rdflib
import simplejson

from django.conf import settings
from django.http import HttpResponse
from django.core.cache import cache
from django.shortcuts import render_to_response
from django.template import RequestContext

from humfrey.utils.views import BaseView, BaseViewMetaclass, renderer
from humfrey.utils import sparql
from humfrey.utils.resource import Resource

class EndpointView(BaseView):
    endpoint = sparql.Endpoint(settings.ENDPOINT_QUERY)

    def get_types(self, uri):
        if ' ' in uri:
            return set()
        key_name = 'types:%s' % hashlib.sha1(uri.encode('utf8')).hexdigest()
        types = cache.get(key_name)
        if types:
            types = pickle.loads(base64.b64decode(types))
        else:
            types = set(rdflib.URIRef(r.type) for r in self.endpoint.query('SELECT ?type WHERE { GRAPH ?g { %s a ?type } }' % uri.n3()))
            cache.set(key_name, base64.b64encode(pickle.dumps(types)), 1800)
        return types

class _RDFViewMetaclass(BaseViewMetaclass):
    @classmethod
    def get_rdf_renderer(mcs, format, mimetype, method, name):
        @renderer(format=format, mimetypes=(mimetype,), name=name)
        def render(self, request, context, template_name):
            graph = context.get('graph')
            if not isinstance(graph, rdflib.ConjunctiveGraph):
                raise NotImplementedError
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
    )

    @renderer(format='kml', mimetypes=('application/vnd.google-earth.kml+xml',), name='KML')
    def render_kml(self, request, context, template_name):
        if not isinstance(context.get('graph'), rdflib.ConjunctiveGraph):
            raise NotImplementedError
        graph = context['graph']
        subjects = set()
        for subject in set(graph.subjects()):
            subject = Resource(subject, graph, self.endpoint)
            if subject.geo_lat and subject.geo_long and isinstance(subject, rdflib.URIRef):
                subjects.add(subject)
        context['subjects'] = subjects
        context['hostname'] = request.META['HTTP_HOST']

        return render_to_response('render.kml',
                                  context, context_instance=RequestContext(request),
                                  mimetype='application/vnd.google-earth.kml+xml')


class ResultSetView(BaseView):
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
                yield '      <binding name="%s">\n' % escape(field)
                yield ' '*8
                value = getattr(result, field)
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
        dumps = simplejson.dumps
        yield '{\n'
        yield '  "head": {\n'
        yield '    "vars": [ %s ]\n' % ', '.join(dumps(v) for v in results.fields)
        yield '  },\n'
        yield '  "results": [\n'
        for i, result in enumerate(results):
            yield '    {' if i == 0 else ',\n    {'
            j = 0
            for name, value in result._asdict().iteritems():
                if value is None:
                    continue
                yield ',\n' if j > 0 else '\n'
                yield '      %s: { "type": ' % dumps(name.encode('utf8'))
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
            yield '\n    }'
        yield '\n  ]\n'
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
        if isinstance(context.get('result'), bool):
            spool = spool_boolean(context['result'])
        elif isinstance(context.get('results'), list):
            spool = spool_resultset(context['results'])
        else:
            raise NotImplementedError
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

