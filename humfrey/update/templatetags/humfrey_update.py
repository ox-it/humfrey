import ansi2html
from django import template
from django.utils.safestring import mark_safe

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


@register.filter(name='ansi2html')
def ansi(value):
    return mark_safe(ansi._conv.convert(value, full=False))
ansi._conv = ansi2html.Ansi2HTMLConverter()


@register.simple_tag(name='ansi2html_styles')
def ansi_styles(scheme='solarized', dark_bg=True):
    return "\n".join(map(str, ansi2html.get_styles(dark_bg, scheme)[1:]))