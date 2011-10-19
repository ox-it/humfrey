import inspect

from django.core.exceptions import ImproperlyConfigured

def pubsub_watcher(channel=None, channels=None):
    if not (channel or channels):
        raise ImproperlyConfigured("Must supply one or other of key and keys")
    channels = channels or ()
    if channel:
        channels += (channel,)

    def decorator(f):
        argspec = inspect.getargspec(f)
        if argspec.args == ['channel', 'data']:
            f._pubsub_watcher_meta = PubSubWatcherMeta(channels=channels)
        else:
            raise ImproperlyConfigured("Callable has wrong argspec (should be (channel, data))")
        return f
    return decorator

class PubSubWatcherMeta(object):
    def __init__(self, channels):
        self.channels = frozenset(channels)
