import base64
import pickle
import threading

import redis

from django.conf import settings

class LonglivingThread(threading.Thread):
    def __init__(self, bail):
        self._bail = bail
        super(LonglivingThread, self).__init__()
    def pack(self, value):
        return base64.b64encode(pickle.dumps(value))
    def unpack(self, value):
        return pickle.loads(base64.b64decode(value))
    def get_redis_client(self):
        return redis.client.Redis(**settings.REDIS_PARAMS)
    def watch_queue(self, client, name, unpack=False):
        while not self._bail.isSet():
            result = client.blpop(name, 2)
            if not result:
                continue
            key, item = result
            if unpack:
                item = self.unpack(item)
                
            yield key, item
                