import urllib
import urlparse
from xml.sax.saxutils import escape

from django import template
from django.template.defaultfilters import linebreaksbr

from humfrey.desc.templatetags.humfrey_desc import sanitize_html

register = template.Library()

def munge_parameter(context, prefix, name, value):
    if prefix:
        key = "%s.%s" % (prefix, name)
    else:
        key = name
    
    url = urlparse.urlparse(context['base_url'])
    query = urlparse.parse_qsl(url.query, True)
    query = dict((k, v) for k, v in query if k != key)
    if value is not None:
        query[key] = value
    # Allows us to remove sub-filters when a super-filter is changed.
    for subkey in context.get('dependent_parameters', {}).get(key, ()):
        query.pop(subkey, None)
    query = sorted(query.iteritems())
    return escape('?' + urllib.urlencode(query))

@register.simple_tag(takes_context=True)
def set_parameter(context, prefix, name, value):
    return munge_parameter(context, prefix, name, value)

@register.simple_tag(takes_context=True)
def remove_parameter(context, prefix, name):
    return munge_parameter(context, prefix, name, None)

@register.filter
def search_html(value):
    if isinstance(value, basestring) and value.startswith('<') and value.endswith('>'):
        return sanitize_html(value)
    else:
        return linebreaksbr(value)
