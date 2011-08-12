import logging, pickle, base64, hashlib

from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.core.urlresolvers import reverse, resolve, NoReverseMatch
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger('core.requests')

from django_conneg.views import ContentNegotiatedView 

class CachedView(ContentNegotiatedView):
    def dispatch(self, request, *args, **kwargs):
        renderers = self.get_renderers(request)
        uri = request.build_absolute_uri()
        
        for renderer in renderers:
            key = hashlib.sha1('pickled-response:%s:%s' % (renderer.format, uri)).hexdigest()
            pickled_response = cache.get(key)
            if pickled_response is not None:
                try:
                    return pickle.loads(base64.b64decode(pickled_response))
                except Exception:
                    pass
            
            response = super(CachedView, self).dispatch(request, *args, **kwargs)
            pickled_response = base64.b64encode(pickle.dumps(response))
            cache.set(key, pickled_response, settings.CACHE_TIMES['page'])
            return response

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
