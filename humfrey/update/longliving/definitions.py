from __future__ import with_statement

import logging
import os
import time

from lxml import etree

from django.conf import settings

from humfrey.longliving.base import LonglivingThread

logger = logging.getLogger(__name__)

class Definitions(LonglivingThread):
    META_NAME = 'update:definition:meta'

    def run(self):
        while True:
            self.update()
            # Check every two seconds to make sure we shouldn't
            # be shutting down. Only update once an hour.
            for i in xrange(1800):
                if self._bail.isSet():
                    return
                time.sleep(2)
        
    def update(self):
        client = self.get_redis_client()
        filenames = set()
        for directory in settings.UPDATE_DEFINITION_DIRECTORIES:
            self.update_directory(client, directory, filenames)
            
        
    
    def update_directory(self, client, directory, filenames):
        for root, dirs, files in os.walk(directory):
            for file in files:
                filename = os.path.join(directory, root, file)
                if not filename.endswith('.hud.xml'):
                    continue
                filenames.add(filename)
                
                logging.debug("Found update definition %r", filename)
                
                mtime = os.stat(filename).st_mtime
                last_mtime = client.hget('update:definition:mtimes', filename)
                if last_mtime and mtime <= self.unpack(last_mtime):
                    continue
                client.hset('update:definition:mtimes', filename, self.pack(mtime))

                logging.info("Parsing update definition %r", filename)
                
                with open(filename, 'r') as f:
                    xml = etree.parse(f)
                
                id = xml.getroot().attrib['id']
                
                item = client.hget(self.META_NAME, id)
                if item:
                    item = self.unpack(item)
                else:
                    item = {
                        'id': id,
                        'last_updated': None,
                        'state': 'inactive',
                    }
                    
                description = xml.xpath('meta/description')
                    
                item.update({
                    'name': xml.xpath('meta/name')[0].text,
                    'filename': filename,
                    'description': description[0].text if description else None,
                })
                
                print item
                
                client.hset(self.META_NAME, id, self.pack(item))

                