import base64
import datetime
from functools import partial
import hashlib
import pickle
from SimpleXMLRPCServer import SimpleXMLRPCDispatcher

import redis

from django.http import HttpResponse, HttpResponseBadRequest
from django.conf import settings
from django.core.urlresolvers import reverse
from django.views.generic import View

from humfrey.utils.views import RedisView
from humfrey.pingback.longliving.pingback_server import NewPingbackHandler, RetrievedPingbackHandler
from django_conneg.views import HTMLView, JSONPView
from django_conneg.http import HttpResponseSeeOther

from .models import InboundPingback

class PingbackView(RedisView):

    class PingbackError(Exception): pass
    class AlreadyRegisteredError(PingbackError): pass

    # The minimum amount of time that must pass before a resubmission is accepted
    resubmission_period = datetime.timedelta(7)

    def ping(self, request, source, target):
        if source == target:
            return HttpResponseBadRequest()

        try:
            pingback = InboundPingback.objects.get(slug=InboundPingback.get_slug(source, target))
        except InboundPingback.DoesNotExist:
            pingback = InboundPingback(source=source, target=target)

        if pingback.updated and pingback.updated + self.resubmission_period > datetime.datetime.now():
            raise self.AlreadyRegisteredError()

        pingback.user_agent = request.META.get('HTTP_USER_AGENT')
        pingback.remote_addr = request.META['REMOTE_ADDR']
        pingback.user = request.user if request.user.is_authenticated() else None

        pingback.queue()

class XMLRPCPingbackView(PingbackView):
    _RESPONSE_CODES = {
        'GENERIC_FAULT': 0x0,
        'SOURCE_NOT_FOUND': 0x10,
        'SOURCE_DOESNT_LINK': 0x11,
        'TARGET_NOT_FOUND': 0x20,
        'TARGET_INVALID': 0x21,
        'ALREADY_REGISTERED': 0x30,
        'ACCESS_DENIED': 0x31,
        'BAD_GATEWAY': 0x32,
    }

    def post(self, request):
        dispatcher = SimpleXMLRPCDispatcher(allow_none=False, encoding=None)
        dispatcher.register_function(partial(self.ping, request), 'pingback:ping')

        response = HttpResponse(mimetype="application/xml")
        response.write(dispatcher._marshaled_dispatch(request.raw_post_data))
        return response

    def ping(self, request, sourceURI, targetURI):
        try:
            super(XMLRPCPingbackView, self).ping(request, sourceURI, targetURI)
        except self.AlreadyRegisteredError:
            return self._RESPONSE_CODES['ALREADY_REGISTERED']
        except self.PingbackError:
            return self._RESPONSE_CODES['GENERIC_FAULT']
        except Exception:
            raise
        else:
            return "OK"

class RESTfulPingbackView(PingbackView):
    def post(self, request):
        try:
            self.ping(request, request.POST['source'], request.POST['target'])
        except Exception:
            return HttpResponseBadRequest()
        else:
            response = HttpResponse()
            response.status_code = 202
            return response

class ModerationView(HTMLView, JSONPView, RedisView):
    def common(self, request):
        client = self.get_redis_client()
        pingback_hashes = ['pingback:item:%s' % s for s in client.smembers(RetrievedPingbackHandler.PENDING_QUEUE_NAME)]
        if pingback_hashes:
            pingbacks = client.mget(pingback_hashes)
            pingbacks = [pickle.loads(base64.b64decode(p)) for p in pingbacks]
            pingbacks.sort(key=lambda d: d['date'])
        else:
            pingbacks = []
        return {
            'client': client,
            'pingbacks': pingbacks,
        }

    def get(self, request):
        context = self.common(request)
        return self.render(request, context, 'pingback/moderation')

    def post(self, request):
        context = self.common(request)
        client = context['client']
        for k in request.POST:
            ping_hash, action = k.split(':')[-1], request.POST[k]
            key_name = 'pingback:item:%s' % ping_hash
            if action in ('accept', 'reject') and not (k.startswith('action:') and client.srem('pingback.pending', ping_hash)):
                continue
            data = pickle.loads(base64.b64decode(client.get(key_name)))
            if action == 'accept':
                data['state'] = 'accepted'
                client.rpush('pingback:accepted', ping_hash)
            else:
                data['state'] = 'rejected'
            client.set(key_name, base64.b64encode(pickle.dumps(data)))
            client.expire(key_name, 3600 * 24 * 7)
        return HttpResponseSeeOther(reverse('pingback:moderation'))
