try:
    try:
        import ujson as json
    except ImportError:
        import simplejson as json
except ImportError:
    import json
