import datetime
import logging
import os
import shutil
import tempfile

from lxml import etree
import pytz

from django.conf import settings

from django_longliving.base import LonglivingThread
from humfrey.update.longliving.definitions import Definitions
from humfrey.update.models import UpdateDefinition
from humfrey.update.transform.base import TransformManager
from humfrey.update.utils import evaluate_pipeline

logger = logging.getLogger(__name__)

class Updater(LonglivingThread):
    UPDATED_CHANNEL = 'humfrey:updater:updated-channel'

    time_zone = pytz.timezone(settings.TIME_ZONE)

    def run(self):
        client = self.get_redis_client()
        transforms = self.get_transforms()

        for _, item in self.watch_queue(client, UpdateDefinition.UPDATE_QUEUE, True):
            logger.info("Item received: %r" % item['config_filename'])
            try:
                self.process_item(client, transforms, item)
            except Exception:
                logger.exception("Exception when processing item")
            logger.info("Item processed: %r" % item['config_filename'])

    def process_item(self, client, transforms, item):
        config_filename = item['config_filename']
        config_file = etree.parse(config_filename)

        if config_file.getroot().tag != 'update-definition':
            raise ValueError("Item specified something that wasn't an update definition")

        id = config_file.getroot().attrib['id']
        definition = client.hget(Definitions.META_NAME, id)
        if definition:
            definition = self.unpack(definition)
            definition['state'] = 'active'
            client.hset(Definitions.META_NAME, id, self.pack(definition))

        variables = dict((e.attrib['name'], e.text) for e in config_file.xpath('parameters/parameter'))

        config_directory = os.path.abspath(os.path.dirname(config_filename))
        graphs_touched = set()

        for pipeline in config_file.xpath('pipeline'):
            output_directory = tempfile.mkdtemp()
            transform_manager = TransformManager(config_directory, output_directory, variables)

            try:
                pipeline = evaluate_pipeline(pipeline.text.strip())
            except SyntaxError:
                raise ValueError("Couldn't parse the given pipeline: %r" % pipeline.text.strip())

            try:
                pipeline(transform_manager)
            finally:
                shutil.rmtree(output_directory)

            graphs_touched |= transform_manager.graphs_touched

        updated = self.time_zone.localize(datetime.datetime.now())

        client.publish(self.UPDATED_CHANNEL,
                       self.pack({'id': id,
                                  'graphs': graphs_touched,
                                  'updated': updated}))

        if definition:
            definition = self.unpack(client.hget(Definitions.META_NAME, id))
            definition['state'] = 'inactive'
            definition['last_updated'] = updated
            client.hset(Definitions.META_NAME, id, self.pack(definition))
