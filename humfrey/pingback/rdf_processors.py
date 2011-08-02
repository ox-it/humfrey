import rdflib

from django_hosts.reverse import reverse_crossdomain

PINGBACK = rdflib.Namespace('http://purl.org/net/pingback/')

def pingback(request, graph, doc_uri, subject_uri, subject, endpoint, renderers):
    graph += [
        (subject_uri, PINGBACK.service, request.build_absolute_uri(reverse_crossdomain('data', 'pingback-xmlrpc'))),
        (subject_uri, PINGBACK.to, request.build_absolute_uri(reverse_crossdomain('data', 'pingback-rest'))),
    ]
