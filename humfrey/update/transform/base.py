import base64
import datetime
import os
import pickle

import redis
from django.conf import settings

from humfrey.sparql.models import Store

class TransformException(Exception):
    pass

class NotChanged(TransformException):
    pass

class NoSuchStore(TransformException):
    pass
class PermissionDeniedToStore(TransformException):
    pass

class Transform(object):
    def get_redis_client(self):
        return redis.client.Redis(**settings.REDIS_PARAMS)
    def pack(self, value):
        return base64.b64encode(pickle.dumps(value))
    def unpack(self, value):
        return pickle.loads(base64.b64decode(value))

    def get_store(self, transform_manager, store, query=False, update=False):
        try:
            store = Store.objects.get(slug=store)
        except Store.DoesNotExist:
            raise NoSuchStore("A store identified by '%s' does not exist." % store)
        if query and not store.can_query(transform_manager.owner):
            raise PermissionDeniedToStore("The owner of this update is not permitted to query the store '%s" % store.slug)
        if update and not store.can_update(transform_manager.owner):
            raise PermissionDeniedToStore("The owner of this update is not permitted to update the store '%s" % store.slug)
        return store

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

class Requires(Transform):
    def __init__(self, first, requirements):
        self._first, self._requirements = first, requirements

    def execute(self, transform_manager, *args):
        for requirement in self._requirements:
            requirement.execute(transform_manager)
        return self._first.execute(transform_manager, *args)
