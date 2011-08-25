from __future__ import with_statement

import shutil

from humfrey.update.transform.base import Transform

class LocalFile(Transform):
    def __init__(self, filename):
        self.filename = filename
    def execute(self, file_manager):
        output = file_manager(self.filename.rsplit('.', 1)[-1])
        file_manager.start(self, [], [output])
        shutil.copy(self.filename, output)
        file_manager.end()
        return output
