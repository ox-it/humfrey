from django.conf import settings

if hasattr(settings, 'STATSD_HOST'):
    from django_statsd.clients import statsd
else:
    # A no-op stub of the statsd interface
    class _timer(object):
        def __call__(self, f):
            return f
        def __enter__(self):
            pass
        def __exit__(self, typ, value, tb):
            pass

    class _statsd(object):
        def decr(self, stat, count=1, rate=1): pass
        def incr(self, stat, count=1, rate=1): pass
        def gauge(self, stat, count=1, rate=1): pass
        def timing(self, stat, delta, rate=1): pass

        def timer(self, stat, rate=1):
            return _timer()

    statsd = _statsd()