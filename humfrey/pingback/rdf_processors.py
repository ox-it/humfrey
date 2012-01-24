import rdflib

from django_hosts.reverse import reverse_full

PINGBACK = rdflib.Namespace('http://purl.org/net/pingback/')

def pingback(request, graph, doc_uri, subject_uri, subject, endpoint, renderers):
    graph += [
        (subject_uri, PINGBACK.service, rdflib.URIRef(request.build_absolute_uri(reverse_full('data', 'pingback:xmlrpc')))),
        (subject_uri, PINGBACK.to, rdflib.URIRef(request.build_absolute_uri(reverse_full('data', 'pingback:rest')))),
    ]
