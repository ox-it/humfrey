import os.path

from .encoding import coerce_triple_iris
from .ntriples import NTriplesSource, NTriplesSink
from .rdfxml import RDFXMLSource, RDFXMLSink

_source_types = {'.nt': NTriplesSource,
                 '.rdf': RDFXMLSource}

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
