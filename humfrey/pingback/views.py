import datetime
from functools import partial
from xmlrpc.server import SimpleXMLRPCDispatcher
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View

from humfrey.sparql.views import StoreView

from .models import InboundPingback

class PingbackView(StoreView):

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
        pingback.user = request.user if request.user.is_authenticated else None
        pingback.store = self.store

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

        response = HttpResponse(content_type="application/xml")
        response.write(dispatcher._marshaled_dispatch(request.body))
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
