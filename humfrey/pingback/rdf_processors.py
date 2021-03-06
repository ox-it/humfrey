import rdflib

from django_hosts.reverse import reverse_full

from humfrey.utils.namespaces import PINGBACK

def pingback(request, context):
    graph, subject = context['graph'], context['subject']
    subject_uri = context['subject']._identifier
    graph += [
        (subject_uri, PINGBACK.service, rdflib.URIRef(request.build_absolute_uri(reverse_full('data', 'pingback:xmlrpc')))),
        (subject_uri, PINGBACK.to, rdflib.URIRef(request.build_absolute_uri(reverse_full('data', 'pingback:rest')))),
    ]
