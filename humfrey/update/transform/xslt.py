from __future__ import with_statement

import subprocess

from humfrey.update.transform.base import Transform

class XSLT(Transform):
    def __init__(self, template, extension='xml'):
        self.template = template
        self.extension = extension
    def execute(self, transform_manager, input):
        template_filename = self.template.execute(transform_manager)

        with open(transform_manager(self.extension), 'w') as output:
            transform_manager.start(self, [template_filename, input], type='xslt')
            subprocess.call(['saxon', input, template_filename],
                            stdout=output)
            transform_manager.end([output.name])
            return output.name