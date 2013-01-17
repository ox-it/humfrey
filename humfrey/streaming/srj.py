import rdflib

from humfrey.sparql.results import Result, SparqlResultList, SparqlResultBool
from humfrey.utils import json

_type_mapping = {'uri': lambda v: rdflib.URIRef(v['value']),
                 'bnode': lambda v: rdflib.BNode(v['value']),
                 'literal': lambda v: rdflib.Literal(v['value'], datatype=v['datatype']),
                 'typed-literal': lambda v: rdflib.Literal(v['value'], language=v.get('xml:lang'))}

class SRJSource(object):
    def __init__(self, stream, encoding='utf-8'):
        self.stream, self.encoding = stream, encoding
    
    def __iter__(self):
        data = json.load(self.stream, self.encoding)
        self.fields = data['head']['vars']
        
        for binding in data['results']['bindings']:
            for name, value in binding.iteritems():
                binding[name] = _type_mapping[value['type'](value)]
            yield Result(self.fields, binding)
