from __future__ import with_statement

from humfrey.update.transform.base import Transform, TransformException
from humfrey.update import models

class NoSuchFile(TransformException):
    pass
class PermissionDeniedToLocalFile(TransformException):
    pass

class LocalFile(Transform):
    def __init__(self, filename):
        self.filename = filename
    def execute(self, transform_manager):
        output = transform_manager(self.filename.rsplit('.', 1)[-1])
        transform_manager.start(self, [])
        try:
            local_file = models.LocalFile.objects.get(name=self.filename)
        except models.LocalFile.DoesNotExist:
            raise NoSuchFile("There is no file by the name of '%s'" % self.filename)
        if not local_file.can_view(transform_manager.owner):
            raise PermissionDeniedToLocalFile("The owner of this update is not permitted to use the file '%s" % self.filename)
        content = local_file.content
        content.open()
        try:
            with open(output, 'w') as f:
                f.write(content.read())
        finally:
            content.close()
        transform_manager.end([output])
        return output
