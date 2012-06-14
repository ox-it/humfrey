from __future__ import with_statement

import logging
import mimetypes
import os
import shutil

from django.conf import settings

from humfrey.update.transform.base import Transform, TransformException
from humfrey.update.tasks import retrieve

logger = logging.getLogger(__name__)

MIMETYPE_OVERRIDES = {'application/xml': 'xml',
                      'application/vnd.ms-excel.12': 'xlsx'}
MIMETYPE_OVERRIDES.update(getattr(settings, 'MIMETYPE_OVERRIDES', {}))

class Retrieve(Transform):
    mimetype_overrides = MIMETYPE_OVERRIDES

    def __init__(self, url, name=None, extension=None, username=None, password=None, auth_type=None):
        self.url, self.name, self.extension = url, name, extension
        self.username, self.password, self.auth_type = username, password, auth_type

    def execute(self, transform_manager):
        filename, headers = retrieve(self.url, self.username, self.password)

        try:
            if not filename:
                raise TransformException(headers.get('message'))

            content_type = headers.get('content-type', 'unknown/unknown')
            content_type = content_type.split(';')[0].strip()
            extension = self.extension \
                     or self.mimetype_overrides.get(content_type) \
                     or (mimetypes.guess_extension(content_type) or '').lstrip('.') \
                     or (mimetypes.guess_extension(content_type, strict=False) or '').lstrip('.') \
                     or 'unknown'

            logger.info("Response had content-type %r; assigning extension %r" % (content_type, extension))

            with open(transform_manager(extension, self.name), 'w') as output:
                transform_manager.start(self, [input], type='identity')
                with open(filename, 'r') as f:
                    shutil.copyfileobj(f, output)

                logger.info("File from %r saved to %r" % (self.url, output.name))
                return output.name
        finally:
            if headers['delete-after']:
                os.unlink(filename)
