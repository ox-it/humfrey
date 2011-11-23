from __future__ import with_statement

import os
import shutil

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from humfrey.update.transform.base import Transform

class LocalFile(Transform):
    def __init__(self, filename):
        self.filename = os.path.normpath(filename)
        if '..' in os.path.split(self.filename):
            raise ValueError('Filename cannot include directory traversals')
    def execute(self, transform_manager):
        if not (transform_manager.transform_directory, getattr(settings, 'UPDATE_TRANSFORM_REPOSITORY', None)):
            raise ImproperlyConfigured("You need to define UPDATE_CACHE_DIRECTORY and UPDATE_TRANSFORM_REPOSITORY settings to use LocalFile.")
        output = transform_manager(self.filename.rsplit('.', 1)[-1])
        transform_manager.start(self, [])
        shutil.copy(os.path.join(transform_manager.transform_directory, self.filename), output)
        transform_manager.end([output])
        return output
