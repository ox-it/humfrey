import rdflib

from humfrey.utils.namespaces import NS
from humfrey.linkeddata.uri import doc_forwards

def formats(request, context):
    graph, subject, doc_uri = context['graph'], context['subject'], context['doc_uri']
    formats_for_context = []
    for renderer in context['renderers']:
        url = rdflib.URIRef(renderer['url'])
        graph += [
            (doc_uri, NS['dcterms'].hasFormat, url),
            (url, NS['dcterms']['title'], rdflib.Literal('%s description of %s' % (renderer['name'], subject.label))),
        ]
        graph += [(url, NS['dc']['format'], rdflib.Literal(mimetype)) for mimetype in renderer['mimetypes']]

    formats_for_context.sort(key=lambda f:f['name'])
    return {
        'formats': formats_for_context,
    }

def doc_meta(request, context):
    doc_uri = context['doc_uri']
    context['graph'] += [
        (doc_uri, NS['foaf'].primaryTopic, context['subject']._identifier),
        (doc_uri, NS['rdf'].type, NS['foaf'].Document),
        (doc_uri, NS['dcterms']['title'], rdflib.Literal('Description of {0}'.format(context['subject'].label)),)
    ]
