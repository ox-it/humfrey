import imp
import os.path

from rdflib import Graph, plugin
from rdflib.parser import Parser
from rdflib.serializer import Serializer

from .base import StreamingParser, StreamingSerializer
from .srx import SRXParser, SRXSerializer
from .srj import SRJParser, SRJSerializer
from .csv import CSVSerializer
from .rdfxml import RDFXMLSerializer
from .ntriples import NTriplesParser, NTriplesSerializer
from .wrapper import get_rdflib_parser, get_rdflib_serializer

from .encoding import coerce_triple_iris

RDFXMLParser = get_rdflib_parser('RDFXMLParser', 'application/rdf+xml', 'xml')

TurtleParser = get_rdflib_parser('TurtleParser', 'text/turtle', 'turtle')
TurtleSerializer = get_rdflib_serializer('TurtleSerializer', 'text/turtle', 'turtle')

N3Parser = get_rdflib_parser('N3Parser', 'text/n3', 'n3')
N3Serializer = get_rdflib_serializer('N3Serializer', 'text/n3', 'n3')


formats = [
    {'format': 'rdf', 'name': 'RDF/XML',
     'parser': RDFXMLParser, 'serializer': RDFXMLSerializer},
    {'format': 'nt', 'name': 'NTriples',
     'parser': NTriplesParser, 'serializer': NTriplesSerializer},
    {'format': 'srj', 'name': 'SPARQL Results JSON', 'priority': 0.9,
     'parser': SRJParser, 'serializer': SRJSerializer},
    {'format': 'srx', 'name': 'SPARQL Results XML',
     'parser': SRXParser, 'serializer': SRXSerializer},
    {'format': 'csv', 'name': 'CSV',
     'parser': None, 'serializer': CSVSerializer},
    {'format': 'ttl', 'name': 'Turtle',
     'parser': TurtleParser, 'serializer': TurtleSerializer},
    {'format': 'n3', 'name': 'Notation3',
     'parser': N3Parser, 'serializer': N3Serializer},
]

# Register the RDF/JSON and JSON-LD serializer plugins if available
try:
    imp.find_module('rdfextras.serializers.rdfjson')
except ImportError:
    pass
else:
    plugin.register("rdf-json", Serializer, 'rdfextras.serializers.rdfjson', 'RdfJsonSerializer')
    RDFJSONSerializer = get_rdflib_serializer('RDFJSONSerializer', 'application/rdf+json', 'rdf-json')
    formats.append({'format': 'rdfjson', 'name': 'RDF/JSON',
                    'parser': None, 'serializer': RDFJSONSerializer})
try:
    imp.find_module('rdfextras.serializers.jsonld')
except ImportError:
    pass
else:
    plugin.register("json-ld", Serializer, 'rdfextras.serializers.jsonld', 'JsonLDSerializer')
    JSONLDSerializer = get_rdflib_parser('JSONLDSerializer', 'application/ld+json', 'json-ld')
    formats.append({'format': 'jsonld', 'name': 'JSON-LD',
                    'parser': None, 'serializer': JSONLDSerializer})

for f in formats:
    f['media_type'] = f['serializer'].media_type
    f['supported_results_types'] = f['serializer'].supported_results_types

parsers = dict((f['media_type'], f['parser']) for f in formats if f.get('parser'))
serializers = dict((f['media_type'], f['serializer']) for f in formats if f.get('serializer'))

def RDFSource(source, parser_kwargs={}):
    """
    Returns an iterator over the triples encoded in source, based on the
    file extension in source.name.
    """
    name, ext = os.path.splitext(source.name)
    if ext in _source_types:
        triples = _source_types[ext](source, parser_kwargs=parser_kwargs)
        return coerce_triple_iris(triples)
    else:
        raise AssertionError("File did not have an expected extension. " +
                             "Was '{0}'; should be one of {1}".format(ext,
                                                                      ', '.join(_source_types)))
