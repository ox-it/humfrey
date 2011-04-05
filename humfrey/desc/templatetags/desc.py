from xml.sax.saxutils import quoteattr, escape

from rdflib import Literal, URIRef


from django import template
from django.utils.safestring import mark_safe

from humfrey.utils.resource import BaseResource

register = template.Library()

@register.filter
def node(obj):
    if isinstance(obj, BaseResource):
        return obj.render()
    elif isinstance(obj, Literal):
        return obj.toPython()
    else:
        return obj
    	
def get_list(r):
	while r and r.rdf_first:
		yield r.rdf_first
		r = r.rdf_rest

@register.filter
def node2(obj):
    if isinstance(obj, BaseResource):
        if obj.owl_unionOf:
            return mark_safe(u'(%s)' % ' &#8746; '.join(map(node2, get_list(obj.get('owl:unionOf')))))
        elif obj.owl_intersectionOf:
            return mark_safe(u'(%s)' % ' &#8746; '.join(map(node2, get_list(obj.get('owl:intersectionOf')))))
        elif isinstance(obj, URIRef):
            return mark_safe(u'<a href="%s">%s</a>' % (quoteattr(obj.doc_url), escape(obj.label2)))
        else:
            return mark_safe(u'<em>unnamed</em>')
    elif isinstance(obj, Literal):
        return obj.toPython()
    else:
        return unicode(obj)