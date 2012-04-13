import urllib
import urlparse

from django import template

register = template.Library()

def munge_parameter(context, prefix, name, value):
    if prefix:
        key = "%s.%s" % (prefix, name)
    else:
        key = name
    
    url = urlparse.urlparse(context['base_url'])
    query = urlparse.parse_qsl(url.query, True)
    query = [(k, v) for k, v in query if k != key]
    if value is not None:
        query.append((key, value))
    query.sort()
    return '?' + urllib.urlencode(query)
    #return urlparse.urlunparse(url)

@register.simple_tag(takes_context=True)
def set_parameter(context, prefix, name, value):
    return munge_parameter(context, prefix, name, value)

@register.simple_tag(takes_context=True)
def remove_parameter(context, prefix, name):
    return munge_parameter(context, prefix, name, None)

