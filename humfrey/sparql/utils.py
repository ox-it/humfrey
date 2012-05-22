import re

from django.conf import settings
from rdflib import URIRef, BNode

from humfrey.utils.namespaces import contract
from .endpoint import Endpoint

IRI = re.compile(u'^([^\\<>"{}|^`\x00-\x20])*$')

label_predicates = ('rdfs:label', 'foaf:name', 'skos:prefLabel', 'dc:title', 'dcterms:title')

def language_key(value):
    if isinstance(value, (URIRef, BNode)):
        return -4
    else:
        return {'en-GB':-3, 'en-US':-2, 'en':-1}.get(value.language, 0)
            
def get_labels(subjects, endpoint=None):
    if not subjects:
        return {}
    if not endpoint:
        endpoint = Endpoint(settings.ENDPOINT_QUERY)
    elif isinstance(endpoint, basestring):
        endpoint = Endpoint(endpoint)
    elif isinstance(endpoint, Endpoint):
        pass
    else:
        raise TypeError("endpoint parameter should be an Endpoint instance.")
    
    subjects = map(URIRef, subjects)
    
    query = """
        CONSTRUCT {
          ?s ?p ?label
        } WHERE {
          ?s ?p ?label .
          FILTER ( %s ) .
          FILTER ( %s )
        }""" % (' || '.join('?s = %s' % s.n3() for s in subjects if s and IRI.match(s)),
                ' || '.join('?p = %s' % p for p in label_predicates))
    
    graph = endpoint.query(query)
    
    labels = {}
    for subject in subjects:
        subject_labels = sorted(graph.objects(subject), key=language_key)
        if subject_labels:
            labels[subject] = subject_labels[0]
        else:
            labels[subject] = contract(subject)
    return labels
