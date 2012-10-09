from xml.sax.saxutils import quoteattr, escape

from lxml import etree
from rdflib import Literal, URIRef, ConjunctiveGraph


from django import template
from django.utils.safestring import mark_safe

from humfrey.linkeddata.uri import doc_forward
from humfrey.linkeddata.resource import BaseResource, Resource
from humfrey.utils.namespaces import NS, expand
import humfrey.utils.templatetags.humfrey_sanitizer

register = template.Library()

@register.filter
def node(obj):
    if isinstance(obj, BaseResource):
        return obj.render()
    elif isinstance(obj, URIRef):
        return Resource(obj, ConjunctiveGraph(), None).render()
    elif isinstance(obj, Literal) and obj.datatype in (NS.xtypes['Fragment-HTML'], NS.rdf['HTML'], NS.xtypes['Fragment-XHTML']):
        return humfrey.utils.templatetags.humfrey_sanitizer.sanitize_html(obj)
    elif isinstance(obj, Literal):
        return mark_safe(escape(unicode(obj.toPython())).replace('\n', '<br/>\n'))
    else:
        return obj

@register.filter
def node_as_plain_text(obj):
    if isinstance(obj, BaseResource):
        return unicode(obj.label)
    if isinstance(obj, Literal):
        return unicode(obj.toPython())
    else:
        return unicode(obj)

def get_list(resource):
    while resource and resource.rdf_first:
        yield resource.rdf_first
        resource = resource.rdf_rest

@register.filter
def node2(obj):
    if isinstance(obj, BaseResource):
        if obj.owl_unionOf:
            return mark_safe(u'(%s)' % ' &#8746; '.join(map(node2, get_list(obj.get('owl:unionOf')))))
        elif obj.owl_intersectionOf:
            return mark_safe(u'(%s)' % ' &#8746; '.join(map(node2, get_list(obj.get('owl:intersectionOf')))))
        elif isinstance(obj, URIRef):
            return mark_safe(u'<a href=%s>%s</a>' % (quoteattr(obj.doc_url), escape(obj.label2)))
        else:
            return mark_safe(u'<em>unnamed</em>')
    elif isinstance(obj, Literal):
        return obj.toPython()
    else:
        return unicode(obj)

@register.filter
def property(obj, value):
    if obj is None:
        return
    return obj.get_one_of(*value.split(','))

@register.filter
def sanitize_html(html, is_xhtml=False):
    return humfrey.utils.templatetags.humfrey_sanitizer.sanitize_html(html, is_xhtml)

@register.filter
def doc_url(uri):
    return doc_forward(uri)

@register.filter
def has_type(obj, value):
    if isinstance(obj, BaseResource):
        return expand(value) in obj.get_all('rdf:type')