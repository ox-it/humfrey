from __future__ import with_statement

import logging
import os
import subprocess
import tempfile

from django.core.exceptions import ImproperlyConfigured

from humfrey.update.transform.base import Transform, TransformException

logger = logging.getLogger(__name__)

class XSLT(Transform):
    def __init__(self, template, extension='xml', params=None):
        self.template = template
        self.extension = extension
        self.params = params or {}

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
            with tempfile.TemporaryFile() as stderr:
                transform_manager.start(self, [template_filename, input], type='xslt')

                popen_args = [self.saxon_path, input, template_filename]

                # Pass the parameters to the template.
                for item in self.params.iteritems():
                    popen_args.append('{0}={1}'.format(*item))

                # Pass the store name to the template, but only if 'store'
                # hasn't been given as a parameter
                if 'store' not in self.params:
                    popen_args.append('store={0}'.format(transform_manager.store.slug))

                returncode = subprocess.call(popen_args, stdout=output, stderr=stderr)

                if stderr.tell():
                    stderr.seek(0)
                    logger.warning("XSLT warnings:\n\n%s\n", stderr.read())

                if returncode != 0:
                    logger.error("XSLT transform failed with code %d", returncode)
                    raise TransformException

                transform_manager.end([output.name])
                return output.name
