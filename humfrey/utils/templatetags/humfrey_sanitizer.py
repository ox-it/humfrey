from django import template
from django.utils.safestring import mark_safe
import rdflib

from humfrey.utils.namespaces import NS
from humfrey.utils import html_sanitizer 

register = template.Library()

@register.filter
def sanitize_html(data, is_xhtml=False):
    if isinstance(data, rdflib.Literal) and data.datatype == NS.xtypes['Fragment-XHTML']:
        is_xhtml = True
    
    return mark_safe(html_sanitizer.sanitize_html(data, is_xhtml))