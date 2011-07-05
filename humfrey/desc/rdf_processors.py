import rdflib

from humfrey.utils.namespaces import NS
from humfrey.linkeddata.uri import doc_forwards

def formats(graph, doc_uri, subject_uri, subject, endpoint, renderers):
    format_urls = doc_forwards(subject_uri, renderers, described=True)
    formats_for_context = []
    for renderer in renderers:
        print renderer
        url = rdflib.URIRef(format_urls[renderer.format])
        formats_for_context.append({
            'url': url,
            'name': renderer.name,
            'mimetypes': renderer.mimetypes,
            'format': renderer.format,
        })
        map(graph.add, [
            (doc_uri, NS['dcterms'].hasFormat, url),
            (url, NS['dcterms']['title'], rdflib.Literal('%s description of %s' % (renderer.name, subject.label))),
        ] + [(url, NS['dc']['format'], rdflib.Literal(mimetype)) for mimetype in renderer.mimetypes]
        )
    formats_for_context.sort(key=lambda f:f['name'])
    return {
        'formats': formats_for_context,
    }

def doc_meta(graph, doc_uri, subject_uri, subject, endpoint, renderers):
    graph += [
        (doc_uri, NS['foaf'].primaryTopic, subject_uri),
        (doc_uri, NS['rdf'].type, NS['foaf'].Document),
        (doc_uri, NS['dcterms']['title'], rdflib.Literal('Description of %s' % subject.label)),
    ]

