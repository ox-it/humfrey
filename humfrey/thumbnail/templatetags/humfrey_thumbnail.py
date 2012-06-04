from xml.sax.saxutils import escape

from django.conf import settings
from django import template
import django_hosts

from humfrey.thumbnail.encoding import encode_parameters

register = template.Library()

THUMBNAIL_URL = getattr(settings, 'THUMBNAIL_URL',
                        ('data', 'thumbnail'))

#@register.simple_tag(takes_context=True)
#def thumbnail(context, url, width=None, height=None):
#    return '{0}?{1}'.format(reverse_full(*THUMBNAIL_URL),
#                            encode_parameters(url, width, height))

@register.tag(name='thumbnail')
def do_thumbnail(parser, token):
    contents = token.split_contents()[1:]
    args, kwargs = [], {}
    for content in contents:
        if '=' in content:
            k, v = content.split('=', 1)
            kwargs[k] = v
        else:
            args.append(content)
    return ThumbnailNode(*args, **kwargs)

class ThumbnailNode(template.Node):
    def __init__(self, url, width=None, height=None):
        self.url = template.Variable(url)
        self.width = int(width) if width else None
        self.height = int(height) if height else None

    def render(self, context):
        url = self.url.resolve(context)
        return escape('{0}?{1}'.format(django_hosts.reverse_full(*THUMBNAIL_URL),
                                encode_parameters(url, self.width, self.height)))