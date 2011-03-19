from rdflib import Namespace

__all__ = 'NS'

NS = {
    'srx': 'http://www.w3.org/2005/sparql-results#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'skos':   'http://www.w3.org/2004/02/skos/core#',
    'foaf':   'http://xmlns.com/foaf/0.1/',
    'fhs':            'http://vocab.ox.ac.uk/fhs/',
    'dc':     'http://purl.org/dc/elements/1.1/',
    'dcterms':    'http://purl.org/dc/terms/',
    'rdfs':   'http://www.w3.org/2000/01/rdf-schema#',
    'v': 'http://www.w3.org/2006/vcard/ns#',
    'geo': 'http://www.w3.org/2003/01/geo/wgs84_pos#',
    'sioc': 'http://rdfs.org/sioc/ns#',
    'doap': 'http://usefulinc.com/ns/doap#',
    'gr': 'http://purl.org/goodrelations/v1#',
    'time': 'http://www.w3.org/2006/time#',
    'xsd': 'http://www.w3.org/2001/XMLSchema#',
    'oxp': 'http://ns.ox.ac.uk/namespace/oxpoints/2009/02/owl#',
    'sdmxdim': 'http://purl.org/linked-data/sdmx/2009/dimension#',
    'qb': 'http://purl.org/linked-data/cube#',
    'void': 'http://rdfs.org/ns/void#',
    'owl': 'http://www.w3.org/2002/07/owl#',
    'cc': 'http://creativecommons.org/ns#',
    'oo': 'http://purl.org/openorg/',
    'ov': 'http://open.vocab.org/terms/',

    # Function namespaces
    'fn': 'http://www.w3.org/2005/xpath-functions#',
    'afn': 'http://jena.hpl.hp.com/ARQ/function#',
}

NS = dict((k,Namespace(v)) for k,v in NS.iteritems())
