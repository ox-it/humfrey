import base64
import pickle

import redis

from django.conf import settings

from django_conneg.views import HTMLView

from humfrey.update.longliving.uploader import Uploader


class IndexView(HTMLView):
    def pack(self, value):
        return base64.b64encode(pickle.dumps(value))
    def unpack(self, value):
        return pickle.loads(base64.b64decode(value))

    def get(self, request):
        client = redis.client.Redis(**settings.REDIS_PARAMS)

        context = {
            'upload_queue': map(self.unpack, client.lrange(Uploader.QUEUE_NAME, 0, 100)),
        }
        
        return self.render(request, context, 'update/index')