from django import template

register = template.Library()

@register.filter
def can_view(obj, user):
    return obj.can_view(user)

@register.filter
def can_change(obj, user):
    return obj.can_change(user)

@register.filter
def can_execute(obj, user):
    return obj.can_execute(user)

@register.filter
def can_delete(obj, user):
    return obj.can_delete(user)

