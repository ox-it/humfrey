import base64
import pickle
import redis

from django.conf import settings
from django.views.generic import View

class RedisView(View):
    @classmethod
    def pack(self, value):
        return base64.b64encode(pickle.dumps(value))
    @classmethod
    def unpack(self, value):
        if value:
            return pickle.loads(base64.b64decode(value))
    @classmethod
    def get_redis_client(self):
        return redis.client.Redis(**settings.REDIS_PARAMS)
