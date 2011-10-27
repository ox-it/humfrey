from __future__ import with_statement

import logging
import os
import subprocess
import sys
import tempfile

from lxml import etree

from django_longliving.base import LonglivingThread
from humfrey.update.longliving.definitions import Definitions

logger = logging.getLogger(__name__)

class CrontabMaintainer(LonglivingThread):
    CRON_DEFINITIONS = 'update:crontab:definitions'
    CRON_LINE = '%(pattern)s HUMFREY_CONFIG_FILE=%(humfrey_config_file)s' \
                         + ' DJANGO_SETTINGS_MODULE=%(django_settings_module)s' \
                         + ' %(executable)s ' \
                         + ' -m humfrey.update.management.commands.update_dataset' \
                         + ' %(filename)s crontab\n'
    TOP_SENTINAL = '# BEGIN maintained by humfrey crontab maintainer\n'
    BOTTOM_SENTINAL = '# END maintained by humfrey crontab maintainer\n'

    def run(self):
        client = self.get_redis_client()
        pubsub = client.pubsub()
        pubsub.subscribe(Definitions.UPDATED_CHANNEL)
        pubsub.subscribe(LonglivingThread.BAIL_CHANNEL)
        try:
            for message in pubsub.listen():
                if self._bail.isSet():
                    break
                if message['channel'] == Definitions.UPDATED_CHANNEL:
                    logger.debug("Definition updates published")
                    changed = self.unpack(message['data'])
                    self.perform_update(client, changed)
        finally:
            pubsub.unsubscribe(Definitions.UPDATED_CHANNEL)
            pubsub.unsubscribe(LonglivingThread.BAIL_CHANNEL)

    def perform_update(self, client, changed):
        cron_definitions = client.get(self.CRON_DEFINITIONS)
        cron_definitions = self.unpack(cron_definitions) if cron_definitions else {}
        for id, filename, xml in changed:
            xml = etree.fromstring(xml)
            pattern = xml.xpath('/update-definition/trigger/cron/@pattern')
            if not pattern and id in cron_definitions:
                del cron_definitions[id]
            elif pattern:
                cron_definitions[id] = {'id': id,
                                        'filename': filename,
                                        'pattern': unicode(pattern[0])}
        client.set(self.CRON_DEFINITIONS, self.pack(cron_definitions))

        crontab_lines = []
        for _, definition in sorted(cron_definitions.iteritems()):
            line = self.CRON_LINE % {
                'pattern': definition['pattern'],
                'humfrey_config_file': os.path.abspath(os.environ['HUMFREY_CONFIG_FILE']),
                'django_settings_module': os.environ['DJANGO_SETTINGS_MODULE'],
                'executable': sys.executable,
                'filename': definition['filename'],
            }
            crontab_lines.append(line)

        crontab_process = subprocess.Popen(['crontab', '-l'], stdout=subprocess.PIPE)
        if crontab_process.wait() == 0:
            crontab = crontab_process.stdout.readlines()
        else:
            crontab = []

        try:
            insert_top = crontab.index(self.TOP_SENTINAL) + 1
            insert_bottom = crontab.index(self.BOTTOM_SENTINAL, insert_top)
        except ValueError:
            if not crontab_lines:
                return # No lines to insert, and there's nothing there anyway.
            crontab.extend(['\n', self.TOP_SENTINAL, self.BOTTOM_SENTINAL])
            insert_top, insert_bottom = -1, -1

        crontab[insert_top:insert_bottom] = crontab_lines

        with tempfile.NamedTemporaryFile() as f:
            f.write(''.join(crontab))
            f.flush()
            subprocess.call(['crontab', f.name])
