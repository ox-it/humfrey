import os
import subprocess

from humfrey.update.transform.base import Transform

class HTMLToXML(Transform):
    def execute(self, transform_manager, input):
        with open(transform_manager('xml'), 'w') as output:
            stderr_filename = output.name[:-3] + 'stderr'
            with open(stderr_filename, 'w') as stderr:
                transform_manager.start(self, [input])
                output_filenames = [output.name]
                
                # Call xmllint to perform the transformation
                subprocess.call(['xmllint', '--html', '--xmlout',
                                            '--dropdtd', '--recover',
                                            '--format', input],
                                stdout=output, stderr=stderr)

                # If something was written to stderr, we add it to our
                # outputs.
                if stderr.tell():
                    output_filenames.append(stderr_filename)

                transform_manager.end(output_filenames)

            # If nothing was written to stderr, it won't be in our
            # outputs, so we can unlink the file.
            if len(output_filenames) == 1:
                os.unlink(stderr_filename)

            return output.name
