from __future__ import with_statement

import os
import subprocess
import StringIO

from django.core.exceptions import ImproperlyConfigured

from humfrey.update.transform.base import Transform, TransformException

class XSLT(Transform):
    def __init__(self, template, extension='xml'):
        self.template = template
        self.extension = extension

    @property
    def saxon_path(self):
        candidates = ['/usr/bin/saxon', '/usr/bin/saxonb-xslt']
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        raise ImproperlyConfigured("Couldn't find saxon.")

    def execute(self, transform_manager, input):
        template_filename = self.template.execute(transform_manager)

        with open(transform_manager(self.extension), 'w') as output:
            transform_manager.start(self, [template_filename, input], type='xslt')

            stderr = StringIO.StringIO()
            returncode = subprocess.call([self.saxon_path, input, template_filename],
                                          stdout=output, stderr=stderr)

            if stderr.tell():
                self.transform_manager.logger.warning("XSLT warnings:\n\n%s\n", stderr.getvalue())

            if returncode != 0:
                self.transform_manager.logger.error("XSLT transform failed with code %d", returncode)
                raise TransformException

            transform_manager.end([output.name])
            return output.name
