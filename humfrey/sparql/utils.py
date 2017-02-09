import itertools
import re

from django.conf import settings
from rdflib import URIRef, BNode, ConjunctiveGraph

from humfrey.utils.namespaces import contract, expand
from .endpoint import Endpoint

IRI = re.compile('^([^\\<>"{}|^`\x00-\x20])*$')

label_predicates = list(map(expand, ('rdfs:label', 'foaf:name', 'skos:prefLabel', 'dc:title', 'dcterms:title')))

def language_key(value):
    if isinstance(value, (URIRef, BNode)):
        return -4
    else:
        return {'en-GB':-3, 'en-US':-2, 'en':-1}.get(value.language, 0)
            
def get_labels(subjects, endpoint=None, mapping=True):
    if not subjects:
        return {}
    if isinstance(subjects, ConjunctiveGraph):
        subjects = itertools.chain(subjects.subjects(),
                                   subjects.predicates(),
                                   subjects.objects())
    if not endpoint:
        from .models import Store, DEFAULT_STORE_SLUG
        endpoint = Endpoint(Store.objects.get(slug=DEFAULT_STORE_SLUG).query_endpoint)
    elif isinstance(endpoint, str):
        endpoint = Endpoint(endpoint)
    elif hasattr(endpoint, 'query'):
        pass
    else:
        raise TypeError("endpoint parameter should be an Endpoint instance.")

    subjects = set(s for s in subjects if isinstance(s, URIRef) and IRI.match(s))

    query = """
        CONSTRUCT {{
          ?s ?p ?label
        }} WHERE {{
          VALUES ?p {{ {predicates} }}
          VALUES ?s {{ {subjects} }}
          ?s ?p ?label
        }}""".format(predicates=' '.join(p.n3() for p in label_predicates),
                     subjects=' '.join(s.n3() for s in subjects))

    graph = endpoint.query(query)
    
    if not mapping:
        return graph

    labels = {}
    for subject in subjects:
        subject_labels = sorted(graph.objects(subject), key=language_key)
        if subject_labels:
            labels[subject] = subject_labels[0]
        else:
            labels[subject] = contract(subject)
    return labels
