from __future__ import with_statement

import logging
import mimetypes
import os
import urllib2

from django.conf import settings

from humfrey import __version__
from humfrey.update.transform.base import Transform, TransformException

logger = logging.getLogger(__name__)

class Retrieve(Transform):
    mimetype_overrides = {
        'application/xml': 'xml',
    }

    def __init__(self, url, name=None, extension=None, username=None, password=None, auth_type=None):
        self.url, self.name, self.extension = url, name, extension
        self.username, self.password, self.auth_type = username, password, auth_type

    def get_opener(self):
        handlers = []
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        if self.username and self.password:
            password_manager.add_password(None, self.url, self.username, self.password)
        if self.auth_type in (None, 'digest'):
            handlers.append(urllib2.HTTPDigestAuthHandler(password_manager))
        if self.auth_type in (None, 'basic'):
            handlers.append(urllib2.HTTPBasicAuthHandler(password_manager))
        return urllib2.build_opener(*handlers)

    def execute(self, transform_manager):
        logger.info("Attempting to retrieve %r" % self.url)
        request = urllib2.Request(self.url)
        request.headers['Accept'] = "application/rdf+xml, text/n3, text/turtle, application/xhtml+xml;q=0.9, text/html;q=0.8"
        request.headers['User-Agent'] = "Mozilla (compatible; humfrey/%s; %s)" % (__version__, settings.DEFAULT_FROM_EMAIL)
        try:
            response = self.get_opener().open(request)
        except (urllib2.HTTPError, urllib2.URLError), e:
            raise TransformException(e)
        logger.info("Response received for %r" % self.url)

        content_type = response.headers.get('Content-Type', 'unknown/unknown')
        content_type = content_type.split(';')[0].strip()
        extension = self.extension \
                 or self.mimetype_overrides.get(content_type) \
                 or (mimetypes.guess_extension(content_type) or '').lstrip('.') \
                 or (mimetypes.guess_extension(content_type, strict=False) or '').lstrip('.') \
                 or 'unknown'

        logger.info("Response had content-type %r; assigning extension %r" % (content_type, extension))

        with open(transform_manager(extension, self.name), 'w') as output:
            transform_manager.start(self, [input], type='identity')
            block_size = os.statvfs(output.name).f_bsize
            while True:
                chunk = response.read(block_size)
                if not chunk:
                    break
                output.write(chunk)
            transform_manager.end([output.name])

            logger.info("File from %r saved to %r" % (self.url, output.name))
            return output.name
