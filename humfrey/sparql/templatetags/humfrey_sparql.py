import rdflib

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def can_administer_store(store, user):
    return user.has_perm(store, 'sparql.administer_store')

@register.filter
def can_query_store(store, user):
    return user.has_perm(store, 'sparql.query_store')

@register.filter
def can_update_store(store, user):
    return user.has_perm(store, 'sparql.update_store')

@register.filter
def uri(v):
    return mark_safe(rdflib.URIRef(v).n3())
