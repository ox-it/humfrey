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

    def __init__(self, url, name=None, extension=None, username=None, password=None, user_agent=None):
        self.url, self.name, self.extension = url, name, extension
        self.username, self.password = username, password
        self.user_agent = user_agent

    def execute(self, transform_manager):
        filename, headers = retrieve(url=self.url,
                                     user=transform_manager.owner,
                                     username=self.username,
                                     password=self.password,
                                     user_agent=self.user_agent)

        try:
            if headers.get('error'):
                raise TransformException("Failed to download %s" % self.url)
            if not filename:
                raise TransformException(headers.get('message'))

            content_type = headers.get('content-type', 'unknown/unknown')
            content_type = content_type.split(';')[0].strip()
            extension = self.extension \
                     or self.mimetype_overrides.get(content_type) \
                     or (mimetypes.guess_extension(content_type) or '').lstrip('.') \
                     or (mimetypes.guess_extension(content_type, strict=False) or '').lstrip('.') \
                     or 'unknown'

            logger.debug("Response had content-type %r; assigning extension %r" % (content_type, extension))

            with open(transform_manager(extension, self.name), 'wb') as output:
                transform_manager.start(self, [input], type='identity')
                with open(filename, 'rb') as f:
                    shutil.copyfileobj(f, output)

                logger.info("File from %r saved to %r" % (self.url, output.name))
                return output.name
        finally:
            if headers['delete-after']:
                os.unlink(filename)
