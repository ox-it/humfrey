import base64
import datetime
import os
import pickle

import redis
from django.conf import settings

class TransformException(Exception):
    pass

class NotChanged(TransformException):
    pass



class Transform(object):
    def get_redis_client(self):
        return redis.client.Redis(**settings.REDIS_PARAMS)
    def pack(self, value):
        return base64.b64encode(pickle.dumps(value))
    def unpack(self, value):
        return pickle.loads(base64.b64decode(value))

    # A mapping from file extensions to rdflib formats.
    rdf_formats = {
        'rdf': 'xml',
        'n3': 'n3',
        'ttl': 'n3',
        'nt': 'nt',
    }

    def __or__(self, other):
        if isinstance(other, type) and issubclass(other, Transform):
            other = other()
        if not isinstance(other, Transform):
            raise AssertionError('%r must be a Transform' % other)

        return Chain(self, other)

    def __call__(self, transform_manager):
        return self.execute(transform_manager)

    def execute(self, update_manager):
        raise NotImplementedError


class Chain(Transform):
    def __init__(self, first, second):
        self._first, self._second = first, second

    def execute(self, transform_manager, *args):
        return self._second.execute(transform_manager,
                                    self._first.execute(transform_manager, *args))
