import base64
import datetime
import pickle

import redis

from django.conf import settings
from django.views.generic.base import View
from django.core.urlresolvers import reverse

from django_conneg.views import HTMLView, JSONView, TextView
from django_conneg.http import HttpResponseSeeOther

from humfrey.update.longliving.uploader import Uploader
from humfrey.update.longliving.updater import Updater
from humfrey.update.longliving.definitions import Definitions

class RedisView(View):
    def pack(self, value):
        return base64.b64encode(pickle.dumps(value))
    def unpack(self, value):
        return pickle.loads(base64.b64decode(value))
    def get_redis_client(self):
        return redis.client.Redis(**settings.REDIS_PARAMS)

class IndexView(HTMLView, RedisView):

    def get(self, request):
        client = self.get_redis_client()
        
        definitions = map(self.unpack, client.hgetall(Definitions.META_NAME).itervalues())
        definitions.sort(key=lambda d:d['name'])
        
        context = {
            'update_definitions': definitions,
            'update_queue': map(self.unpack, client.lrange(Updater.QUEUE_NAME, 0, 100)),
            'upload_queue': map(self.unpack, client.lrange(Uploader.QUEUE_NAME, 0, 100)),
        }
        
        return self.render(request, context, 'update/index')

class TriggerView(JSONView, HTMLView, TextView, RedisView):
    def post(self, request, id=None):
        context = {}
        
        self.perform_update(request, context, id)

        renderers = self.get_renderers(request)
        if not context.get('status-code') and renderers and renderers[0].format == 'html':
            return HttpResponseSeeOther(reverse('update-index'))
        else:
            return self.render(request, context, 'update/trigger')

    def perform_update(self, request, context, id):
        id = id or request.POST.get('id')
        if not id:
            context.update({
                'error': 'You must specify an `id` parameter.',
                'status_code': 400,
            })
            return
        
        client = self.get_redis_client()
        item = client.hget(Definitions.META_NAME, id)
        print "IT", id, item
        if item:
            item = self.unpack(item)
            client.rpush(Updater.QUEUE_NAME, self.pack({
                'config_filename': item['filename'],
                'name': item['name'],
                'trigger': 'web',
                'remote_user': request.META.get('REMOTE_USER'),
                'queued_at': datetime.datetime.now(),
            }))
        else:
            context.update({
                'error': 'Unknown update definition `id`.',
                'status_code': 404,
            })

 