import logging
import subprocess
import tempfile

from django.conf import settings

from .base import Transform, TransformException

SHELL_TRANSFORMS = getattr(settings, 'SHELL_TRANSFORMS', {})

logger = logging.getLogger(__name__)

class Shell(Transform):
    def __init__(self, name, extension, params=None):
        self.shell = SHELL_TRANSFORMS[name]
        self.extension = extension
        self.params = params or {}

    def execute(self, transform_manager, input):
        params = self.params.copy()
        if 'store' not in params:
            params['store'] = transform_manager.store.slug

        popen_args = [input if arg is None else arg.format(params) for arg in self.shell]

        with open(transform_manager(self.extension), 'wb') as output:
            with tempfile.TemporaryFile() as stderr:
                transform_manager.start(self, [input])

                returncode = subprocess.call(popen_args, stdout=output, stderr=stderr)

                if stderr.tell():
                    stderr.seek(0)
                    logger.warning("Shell warnings:\n\n%s\n", stderr.read())

                if returncode != 0:
                    logger.error("Shell transform failed with code %d", returncode)
                    raise TransformException

                transform_manager.end([output.name])
                return output.name
