import rdflib

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def can_administer_store(store, user):
    return store.can_administer(user)

@register.filter
def can_query_store(store, user):
    return store.can_query(user)

@register.filter
def can_update_store(store, user):
    return store.can_update(user)

@register.filter
def uri(v):
    return mark_safe(rdflib.URIRef(v).n3())
