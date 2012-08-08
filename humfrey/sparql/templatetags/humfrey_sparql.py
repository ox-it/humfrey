from django import template

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

