from rdflib import Literal

from django import template

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