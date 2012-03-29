import os.path

from .ntriples import NTriplesSource, NTriplesSink
from .rdfxml import RDFXMLSource, RDFXMLSink

def RDFSource(source):
    name, ext = os.path.splitext(source.name)
    print name, ext
    if ext == '.nt':
        return NTriplesSource(source)
    elif ext == '.rdf':
        return RDFXMLSource(source)
    else:
        raise AssertionError
