import logging

from django.conf import settings
from django.utils.importlib import import_module
from django.core.exceptions import ImproperlyConfigured

from humfrey.longliving.base import LonglivingThread
from humfrey.longliving.decorators import PubSubWatcherMeta
logger = logging.getLogger(__name__)

class PubSubDispatcherThread(LonglivingThread):
    def run(self):
        client = self.get_redis_client()

        self._watchers, self._keys = self._get_watchers(client)

        pubsub = client.pubsub()
        pubsub.subscribe(LonglivingThread.BAIL_CHANNEL)
        logger.debug("Subscribing to %d channels", len(self._keys))
        for key in self._keys:
            pubsub.subscribe(key)

        try:
            for message in pubsub.listen():
                if self._bail.isSet():
                    break
                channel, data = message['channel'], self.unpack(message['data'])
                for watcher in self._watchers:
                    if channel in watcher['meta'].channels:
                        try:
                            watcher['callable'](channel, data)
                        except Exception:
                            logger.exception("PubSub watcher exited unexpectedly")

        finally:
            pubsub.unsubscribe(LonglivingThread.BAIL_CHANNEL)
            for key in self._keys:
                pubsub.unsubscribe(key)



    def _get_watchers(self, client):
        paths = getattr(settings, 'PUBSUB_WATCHERS', ())

        watchers, channels = [], set()
        for path in paths:
            module_path, callable_name = path.rsplit('.', 1)
            module = import_module(module_path)
            callable = getattr(module, callable_name)
            meta = getattr(callable, '_pubsub_watcher_meta')
            if not isinstance(meta, PubSubWatcherMeta):
                raise ImproperlyConfigured("%r hasn't been decorated with @pubsub_watcher" % path)

            watchers.append({'callable': callable,
                             'meta': meta})
            channels |= meta.channels

        return watchers, channels
