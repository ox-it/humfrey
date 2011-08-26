from __future__ import with_statement

import mimetypes
import os
import urllib2

from humfrey.update.transform.base import Transform


class Retrieve(Transform):
    mimetype_overrides = {
        'application/xml': 'xml',
    }

    def __init__(self, url):
        self.url = url

    def execute(self, transform_manager):
        response = urllib2.urlopen(self.url)
        
        content_type = response.headers.get('Content-Type', 'unknown/unknown')
        content_type = content_type.split(';')[0].strip()
        extension = self.mimetype_overrides.get(content_type) \
                 or (mimetypes.guess_extension(content_type) or '').lstrip('.') \
                 or (mimetypes.guess_extension(content_type, strict=False) or '').lstrip('.') \
                 or 'unknown'
            
        with open(transform_manager(extension), 'w') as output:
            transform_manager.start(self, [input], [output], type='identity')
            block_size = os.statvfs(output.name).f_bsize
            while True:
                chunk = response.read(block_size)
                if not chunk:
                    break
                output.write(chunk)
            transform_manager.end()
            return output.name