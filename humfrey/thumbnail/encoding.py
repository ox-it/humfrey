from hashlib import sha256
import urllib.request, urllib.parse, urllib.error

from django.conf import settings


def encode_parameters(url, width=None, height=None):
    params = [('key', settings.SECRET_KEY),
              ('url', url)]
    if width:
        params.append(('width', width))
    if height:
        params.append(('height', height))
    query_string = urllib.parse.urlencode(params)
    params.append(('s', sha256(query_string.encode()).hexdigest()))
    params.pop(0) # Remove the key
    return urllib.parse.urlencode(params)
