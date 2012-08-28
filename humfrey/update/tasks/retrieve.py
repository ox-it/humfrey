from hashlib import sha1
import httplib
import json
import logging
import os
import shutil
import tempfile
import urllib2

from celery.task import task
from django.conf import settings

from humfrey import __version__, source_homepage

DOWNLOAD_CACHE = getattr(settings, 'DOWNLOAD_CACHE', None)

USER_AGENTS = {'agent': 'humfrey/{0} ({1}; {2})'.format(__version__, source_homepage, settings.DEFAULT_FROM_EMAIL),
               'browser': 'Mozilla (compatible; humfrey/{0}; {1}; {2})'.format(__version__, source_homepage, settings.DEFAULT_FROM_EMAIL)}

logger = logging.getLogger(__name__)

def get_filename(url):
    h = sha1(url).hexdigest()
    return os.path.join(DOWNLOAD_CACHE, h[:2], h[2:4], h)

def get_opener(url, user, username, password):
    handlers = []
    password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
    if username and password:
        password_manager.add_password(None, url, username, password)
    if user and user.is_authenticated():
        for credential in user.credential_set.all():
            logger.debug("Adding credential %s %s", credential.url, credential.username)
            password_manager.add_password(None, credential.url, credential.username, credential.password)
    handlers.append(urllib2.HTTPDigestAuthHandler(password_manager))
    handlers.append(urllib2.HTTPBasicAuthHandler(password_manager))
    return urllib2.build_opener(*handlers)


@task(name='humfrey.update.retrieve')
def retrieve(url, headers=None, user=None, username=None, password=None, user_agent=None):
    headers = headers or {}
    opener = get_opener(url, user, username, password)

    request = urllib2.Request(url)
    request.add_header('User-Agent', USER_AGENTS.get(user_agent or 'browser', user_agent))
    request.add_header('Accept', "application/rdf+xml, text/n3, text/turtle, application/xhtml+xml;q=0.9, text/html;q=0.8")
    for key in headers:
        request.add_header(key, headers[key])

    filename = get_filename(url)
    headers_filename = filename + '.headers'

    if os.path.exists(headers_filename):
        with open(headers_filename) as f:
            previous_headers = json.load(f)
    else:
        previous_headers = {}

    if 'last-modified' in previous_headers:
        request.add_header('If-Modified-Since', previous_headers['last-modified'])
    if 'etag' in previous_headers:
        request.add_header('If-None-Match', previous_headers['etag'])

    try:
        response = opener.open(request)
    except urllib2.HTTPError, e:
        response = e
    except urllib2.URLError, e:
        logger.exception("Couldn't retrieve %s: %s", url, e)
        return None, {'error': True,
                      'message': str(e),
                      'delete-after': False}
    headers = dict((k.lower(), response.headers[k]) for k in response.headers)
    headers['status'] = response.code
    headers['url'] = response.url
    headers['error'] = response.code >= 400

    if response.code == httplib.OK:
        logger.debug("Cache miss: %s", url)

        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        with open(filename, 'w') as f:
            shutil.copyfileobj(response, f)

        h = sha1()
        with open(filename, 'r') as f:
            chunk = f.read(4096)
            while chunk:
                h.update(chunk)
                chunk = f.read(4096)

        with open(headers_filename, 'w') as f:
            headers['sha1'] = h.hexdigest()
            headers['delete-after'] = False
            json.dump(headers, f)
            
        headers['from-cache'] = False
        return filename, headers

    elif response.code == httplib.NOT_MODIFIED:
        logger.debug("Cache hit: %s", url)

        previous_headers['from-cache'] = True
        previous_headers['delete-after'] = False
        return filename, previous_headers
    else:
        logger.debug("Error: %d, %s", response.code, url)
        headers['delete-after'] = True
        headers['from-cache'] = False
        headers['error'] = True
        with tempfile.NamedTemporaryFile(delete=False) as f:
            shutil.copyfileobj(response, f)
        return f.name, headers
