from __future__ import with_statement

import subprocess

from humfrey.update.transform.base import Transform

class HTMLToXML(Transform):
    def execute(self, transform_manager, input):
        with open(transform_manager('xml'), 'w') as output:
            transform_manager.start(self, [input], [output])
            subprocess.call(['xmllint', '--html', '--xmlout',
                                        '--dropdtd', '--recover',
                                        '--format', input],
                            stdout=output)
            transform_manager.end()
            return output.name