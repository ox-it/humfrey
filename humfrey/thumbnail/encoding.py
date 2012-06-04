from hashlib import sha256
import urllib

from django.conf import settings

def encode_parameters(url, width=None, height=None):
    params = [('key', settings.SECRET_KEY),
              ('url', url)]
    if width:
        params.append(('width', width))
    if height:
        params.append(('height', height))
    query_string = urllib.urlencode(params)
    params.append(('s', sha256(query_string).hexdigest()))
    params.pop(0) # Remove the key
    return urllib.urlencode(params)
