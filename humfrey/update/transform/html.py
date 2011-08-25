from __future__ import with_statement

import subprocess

from humfrey.update.transform.base import Transform

class HTMLToXML(Transform):
    def execute(self, file_manager, input):
        with open(file_manager('xml'), 'w') as output:
            file_manager.start(self, [input], [output])
            subprocess.call(['xmllint', '--html', '--xmlout',
                                        '--dropdtd', '--recover',
                                        '--format', input],
                            stdout=output)
            file_manager.end()
            return output.name