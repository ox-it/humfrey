import os.path

from .ntriples import NTriplesSource, NTriplesSink
from .rdfxml import RDFXMLSource, RDFXMLSink

_source_types = {'.nt': NTriplesSource,
                 '.rdf': RDFXMLSource}

def RDFSource(source):
    """
    Returns an iterator over the triples encoded in source, based on the
    file extension in source.name.
    """
    name, ext = os.path.splitext(source.name)
    if ext in _source_types:
        return _source_types[ext](source)
    else:
        raise AssertionError("File did not have an expected extension. " +
                             "Was '{0}'; should be one of {1}".format(ext,
                                                                      ', '.join(_source_types)))
