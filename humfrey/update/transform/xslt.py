from __future__ import with_statement

import subprocess

from humfrey.update.transform.base import Transform

class XSLT(Transform):
    def __init__(self, template, extension='xml'):
        self.template = template
        self.extension = extension
    def execute(self, file_manager, input):
        template_filename = self.template.execute(file_manager)

        with open(file_manager(self.extension), 'w') as output:
            file_manager.start(self, [template_filename, input], [output], type='xslt')
            subprocess.call(['saxon', input, template_filename],
                            stdout=output)
            return output.name