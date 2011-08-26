from __future__ import with_statement

import os
import shutil

from humfrey.update.transform.base import Transform

class LocalFile(Transform):
    def __init__(self, filename):
        self.filename = filename
    def execute(self, transform_manager):
        if os.sep in self.filename:
            raise ValueError('Filename cannot include directory traversals')
        output = transform_manager(self.filename.rsplit('.', 1)[-1])
        transform_manager.start(self, [], [output])
        shutil.copy(os.path.join(transform_manager.config_directory, self.filename), output)
        transform_manager.end()
        return output
