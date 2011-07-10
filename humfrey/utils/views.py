from inspect import isfunction
import logging, itertools, pickle, base64, hashlib
from datetime import datetime, date

import simplejson
from lxml import etree

from django.db import models
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseForbidden, Http404
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse, resolve, NoReverseMatch
from django.core.cache import cache

logger = logging.getLogger('core.requests')

from .http import MediaType
from .simplify import simplify_value, simplify_model, serialize_to_xml

def renderer(format, mimetypes=(), priority=0, name=None):
    """
    Decorates a view method to say that it renders a particular format and mimetypes.

    Use as:
        @renderer(format="foo")
        def render_foo(self, request, context, template_name): ...
    or
        @renderer(format="foo", mimetypes=("application/x-foo",))
        def render_foo(self, request, context, template_name): ...
    
    The former case will inherit mimetypes from the previous renderer for that
    format in the MRO. Where there isn't one, it will default to the empty
    tuple.

    Takes an optional priority argument to resolve ties between renderers.
    """

    def g(f):
        f.is_renderer = True
        f.format = format
        f.mimetypes = set(MediaType(mimetype, priority) for mimetype in mimetypes)
        f.name = name
        return f
    return g

class BaseViewMetaclass(type):
    def __new__(cls, name, bases, dict):

        # Pull the renderers from the bases into a couple of new dicts for
        # this view's renderers
        formats_by_mimetype = {}
        formats = {}
        for base in reversed(bases):
            if hasattr(base, 'FORMATS'):
                formats.update(base.FORMATS)
                formats_by_mimetype.update(base.FORMATS_BY_MIMETYPE)

        for key, value in dict.items():
            # If the method is a renderer we add it to our dicts. We can't add
            # the functions right now because we want them bound to the view
            # instance that hasn't yet been created. Instead, add the keys (strs)
            # and we'll replace them with the bound instancemethods in BaseView.__init__.
            if isfunction(value) and getattr(value, 'is_renderer', False):
                if value.mimetypes is not None:
                    mimetypes = value.mimetypes
                elif value.format in formats:
                    mimetypes = formats[value.format].mimetypes
                else:
                    mimetypes = ()
                for mimetype in mimetypes:
                    formats_by_mimetype[mimetype] = key
                formats[value.format] = key

        dict.update({
            'FORMATS': formats,
            'FORMATS_BY_MIMETYPE': formats_by_mimetype,
        })

        # Create our view.
        view = type.__new__(cls, name, bases, dict)

        return view


class BaseView(object):
    __metaclass__ = BaseViewMetaclass

    ALLOWABLE_METHODS = ('GET', 'POST', 'DELETE', 'HEAD', 'OPTIONS', 'PUT')

    def method_not_allowed(self, request):
        return HttpResponseNotAllowed([m for m in self.ALLOWABLE_METHODS if hasattr(self, 'handle_%s' % m)])

    def not_acceptable(self, request):
        response = HttpResponse("The desired media type is not supported for this resource.", mimetype="text/plain")
        response.status_code = 406
        return response

    def bad_request(self, request):
        response = HttpResponse(
            'Your request was malformed.',
            status=400,
        )
        return response

    def initial_context(self, request, *args, **kwargs):
        return {}
    
    def __init__(self):
        # Resolve renderer names to bound instancemethods. Also turn the
        # FORMATS_BY_MIMETYPE dict into a list of pairs ordered by descending priority.
        self.FORMATS = dict((key, getattr(self, value)) for key, value in self.FORMATS.items())
        formats_sorted = sorted(self.FORMATS_BY_MIMETYPE.items(), key=lambda x: x[0].priority, reverse=True)
        self.FORMATS_BY_MIMETYPE = tuple((key, getattr(self, value)) for (key, value) in formats_sorted)
    
    def __unicode__(self):
        cls = type(self)
        return ".".join((cls.__module__, cls.__name__))

    def __call__(self, request, *args, **kwargs):
        method_name = 'handle_%s' % request.method
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            request.renderers = self.get_renderers(request)
            if request.renderers and request.renderers[0].format == 'html' and \
               getattr(method, 'cached', False) and request.method in ('GET', 'HEAD') and not request.GET:
                key = hashlib.sha1('pickled-response:%s' % request.build_absolute_uri()).hexdigest()
                pickled_response = cache.get(key)
                if pickled_response is not None:
                    try:
                        return pickle.loads(base64.b64decode(pickled_response))
                    except Exception:
                        pass
                context = self.initial_context(request, *args, **kwargs)
                response = method(request, context, *args, **kwargs)
                pickled_response = base64.b64encode(pickle.dumps(response))
                cache.set(key, pickled_response, settings.CACHE_TIMES['page'])
                return response
            context = self.initial_context(request, *args, **kwargs)
            response = method(request, context, *args, **kwargs)
            return response
        else:
            return self.method_not_allowed(request)

    def handle_HEAD(self, request, *args, **kwargs):
        """
        Provides a default HEAD handler that strips the content from the
        response returned by the GET handler.
        """
        if hasattr(self, 'handle_GET'):
            response = self.handle_GET(request, *args, **kwargs)
        else:
            response = self.method_not_acceptable(request)
        response.content = ''
        return response

    def get_zoom(self, request, default=16):
        try:
            zoom = int(request.GET['zoom'])
        except (ValueError, KeyError):
            zoom = default
        else:
            zoom = min(max(10, zoom), 18)
        return zoom
        
    def get_renderers(self, request):
        if 'format' in request.REQUEST:
            formats = request.REQUEST['format'].split(',')
            renderers, seen_formats = [], set()
            for format in formats:
                if format in self.FORMATS and format not in seen_formats:
                    renderers.append(self.FORMATS[format])
        elif request.META.get('HTTP_ACCEPT'):
            accepts = self.parse_accept_header(request.META['HTTP_ACCEPT'])
            renderers = MediaType.resolve(accepts, self.FORMATS_BY_MIMETYPE)
        else:
            renderers = [self.FORMATS['html']]
        return renderers
    	

    def render(self, request, context, template_name):

        status_code = context.pop('status_code', 200)

        for renderer in request.renderers:
            try:
                response = renderer(request, context, template_name)
                response.status_code = status_code
                response['Access-Control-Allow-Origin'] = '*'
                return response
            except NotImplementedError:
                continue
        else:
            tried_mimetypes = list(itertools.chain(*[r.mimetypes for r in request.renderers]))
            response = HttpResponse("""\
Your Accept header didn't contain any supported media ranges.

Supported ranges are:

 * %s\n""" % '\n * '.join(sorted('%s (%s)' % (f[0].value, f[1].format) for f in self.FORMATS_BY_MIMETYPE if not f[0] in tried_mimetypes)), mimetype="text/plain")
            response.status_code = 406 # Not Acceptable
            return response

    @classmethod
    def parse_accept_header(cls, accept):
        media_types = []
        for media_type in accept.split(','):
            try:
                media_types.append(MediaType(media_type))
            except ValueError:
                pass
        return media_types

    def render_to_format(self, request, context, template_name, format):
        render_method = self.FORMATS[format]
        status_code = context.pop('status_code', 200)
        response = render_method(request, context, template_name)
        response.status_code = status_code
        return response

    #@renderer(format="json", mimetypes=('application/json',), name='JSON')
    def render_json(self, request, context, template_name):
        callback = request.GET.get('callback', request.GET.get('jsonp', None))
        context = simplify_value(context)
        content = simplejson.dumps(context)
        if callback:
            content = '%s(%s);' % (callback, content)
            mimetype = 'application/javascript'
        else:
            mimetype = 'application/json'

        return HttpResponse(content, mimetype=mimetype)

    #@renderer(format="js", mimetypes=('text/javascript','application/javascript',), name='JavaScript')
    def render_js(self, request, context, template_name):
        callback = request.GET.get('callback', request.GET.get('jsonp', 'callback'))
        content = simplejson.dumps(simplify_value(context))
        content = "%s(%s);" % (callback, content)
        return HttpResponse(content, mimetype="application/javascript")

    @renderer(format="html", mimetypes=('text/html', 'application/xhtml+xml'), priority=1, name='HTML')
    def render_html(self, request, context, template_name):
        if template_name is None:
            raise NotImplementedError
        return render_to_response(template_name+'.html',
                                  context, context_instance=RequestContext(request),
                                  mimetype='text/html')

    #@renderer(format="xml", mimetypes=('application/xml', 'text/xml'), name='XML')
    def render_xml(self, request, context, template_name):
        context = simplify_value(context)
        return HttpResponse(etree.tostring(serialize_to_xml(context), encoding='UTF-8'), mimetype="application/xml")

    # We don't want to depend on YAML. If it's there offer it as a renderer, otherwise ignore it.
    try:
        __import__('yaml') # Try importing, but don't stick the result in locals.
        @renderer(format="yaml", mimetypes=('application/x-yaml',), priority=-1, name='YAML')
        def render_yaml(self, request, context, template_name):
            import yaml
            context = simplify_value(context)
            return HttpResponse(yaml.safe_dump(context), mimetype="application/x-yaml")
    except ImportError, e:
        pass



def ReverseView(request):
    try:
        name = request.GET['name']
        args = request.GET.getlist('arg')
        
        path = reverse(name, args=args)
        view, view_args, view_kwargs = resolve(path)
        return HttpResponse("http://%s%s" % (
            request.META['HTTP_HOST'],
            path,
        ), mimetype='text/plain')
    except NoReverseMatch:
        raise Http404
    except KeyError:
        return HttpResponseBadRequest()
