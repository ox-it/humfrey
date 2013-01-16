from rdflib import ConjunctiveGraph, URIRef, BNode, Literal

from humfrey.linkeddata.resource import Resource
from humfrey.sparql.results import Result, SparqlResultList, SparqlResultBool, SparqlResultGraph
from humfrey.utils import json

class SRJSource(object):
    def __init__(self, stream, encoding='utf-8'):
        return self.parse_json_results(stream)

    def parse_json_results(self, response):
        graph = ConjunctiveGraph()
        data = json.load(response)

        if 'boolean' in data:
            return SparqlResultBool(data['boolean'])

        vars_ = data['head']['vars']
        ResultClass = Result(data['head']['vars'])
        pb = self.parse_json_binding

        results = SparqlResultList(vars_)
        for binding in data['results']['bindings']:
            results.append(ResultClass(*[pb(binding.get(v), graph) for v in vars_]))
        return results

    def parse_json_binding(self, binding, graph):
        if not binding:
            return None
        t = binding['type']
        if t == 'uri':
            return URIRef(binding['value'])
        elif t == 'bnode':
            return BNode(binding['value'])
        elif t == 'literal':
            return Literal(binding['value'], lang=binding.get('lang'))
        elif t == 'typed-literal':
            return Literal(binding['value'], datatype=binding.get('datatype'))
        else:
            raise AssertionError("Unexpected binding type")
