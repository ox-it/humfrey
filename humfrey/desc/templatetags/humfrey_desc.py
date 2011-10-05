from xml.sax.saxutils import quoteattr, escape

from lxml import etree
from rdflib import Literal, URIRef


from django import template
from django.utils.safestring import mark_safe

from humfrey.linkeddata.uri import doc_forward
from humfrey.utils.resource import BaseResource
from humfrey.utils.namespaces import NS

register = template.Library()

@register.filter
def node(obj):
    if isinstance(obj, BaseResource):
        return obj.render()
    elif isinstance(obj, Literal) and obj.datatype == NS.xtypes['Fragment-XHTML']:
        return mark_safe(sanitize_html(unicode(obj)))
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


def sanitize_html(html):
    good_attribs = 'src href alt title'.split()
    good_tags = 'ul li em strong u b div span ol i dl dt dd table tbody thead tfoot tr td th hr img p br'.split()
    remove_tags = 'iframe'.split()
    block_tags = ''.split()

    def sanitize(elem):
        for key in list(elem.attrib):
            if key not in good_attribs:
                del elem.attrib[key]
            if key == 'href':
                elem.attrib['rel'] = 'nofollow'
        if elem.tag not in good_tags:
            elem.tag = 'div' if elem.tag in block_tags else 'span'
        for child in elem:
            sanitize(child)
        return elem

    return etree.tostring(sanitize(etree.fromstring(html)))

@register.filter
def doc_url(uri):
    return doc_forward(uri)
