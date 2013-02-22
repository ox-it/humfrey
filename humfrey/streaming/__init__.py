import imp
import os.path

from rdflib import Graph, plugin

try: # rdflib 3.x
    from rdflib.serializer import Serializer
except ImportError: # rdflib 2.4
    from rdflib.syntax.serializers import Serializer

from .base import StreamingParser, StreamingSerializer
from .srx import SRXParser, SRXSerializer
from .srj import SRJParser, SRJSerializer
from .csv import CSVSerializer
from .rdfxml import RDFXMLSerializer
from .ntriples import NTriplesParser, NTriplesSerializer
from .xls import XLSSerializer
from .wrapper import get_rdflib_parser, get_rdflib_serializer

from .encoding import coerce_triple_iris

RDFXMLParser = get_rdflib_parser('RDFXMLParser', 'application/rdf+xml', 'xml',
                                 parser_kwargs={'preserve_bnode_ids': True})

try: # rdflib 3.x
    TurtleParser = get_rdflib_parser('TurtleParser', 'text/turtle', 'turtle')
except Exception: # rdflib 2.4
    TurtleParser = get_rdflib_parser('TurtleParser', 'text/turtle', 'n3')
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
    {'format': 'xls', 'name': 'Excel Spreadsheet (XLS)',
     'parser': None, 'serializer': XLSSerializer},
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

def format_by_extension(ext):
    ext = ext.rsplit('.', 1)[-1]
    for format_spec in formats:
        if format_spec['format'] == ext:
            return format_spec
    raise KeyError(ext)

def parser_by_extension(ext):
    return format_by_extension(ext)['parser']
def serializer_by_extension(ext):
    return format_by_extension(ext)['serializer']

def parse(f, extension=None):
    parser = parser_by_extension(extension or f.name)
    return parser(f)

def serialize(data, f, extension=None):
    serializer = serializer_by_extension(extension or f.name)
    serializer(data).serialize(f)
