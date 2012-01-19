import contextlib
import datetime
import logging
import os
import shutil
import StringIO
import tempfile
import urlparse

import pytz

from django.conf import settings

from django_longliving.base import LonglivingThread
from humfrey.update.models import UpdateDefinition
from humfrey.update.transform.base import NotChanged, TransformException
from humfrey.update.utils import evaluate_pipeline

logger = logging.getLogger(__name__)

class TransformManager(object):
    def __init__(self, update_log, output_directory, parameters, force=False):
        self.update_log = update_log
        self.owner = update_log.update_definition.owner
        self.output_directory = output_directory
        self.parameters = parameters
        self.force = force
        self.logger = logging.getLogger('%s.%s' % (__name__, update_log.pk))
        self.log_stream = StringIO.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.logger.addHandler(self.handler)

        self.counter = 0
        self.transforms = []
        self.graphs_touched = set()

    def __call__(self, extension):
        filename = os.path.join(self.output_directory, '%s.%s' % (self.counter, extension))
        self.counter += 1
        return filename

    def start(self, transform, inputs, type='generic'):
        self.current = {'transform': transform,
                        'inputs': inputs,
                        'start': datetime.datetime.now(),
                        'type': type}
    def end(self, outputs):
        self.current['end'] = datetime.datetime.now()
        self.current['outputs'] = outputs
        self.transforms.append(self.current)
        del self.current
    def touched_graph(self, graph_name):
        self.graphs_touched.add(graph_name)
    def not_changed(self):
        if not self.force:
            raise NotChanged()

class Updater(LonglivingThread):
    UPDATED_CHANNEL = 'humfrey:updater:updated-channel'

    time_zone = pytz.timezone(settings.TIME_ZONE)

    def run(self):
        client = self.get_redis_client()

        for _, update_log in self.watch_queue(client, UpdateDefinition.UPDATE_QUEUE, True):
            logger.info("Item received: %r" % update_log.update_definition.slug)
            try:
                with self.logged(update_log):
                    self.process_item(client, update_log)
            except Exception:
                logger.exception("Exception when processing item")
            logger.info("Item processed: %r" % update_log.update_definition.slug)

    @contextlib.contextmanager
    def logged(self, update_log):
        update_log.started = datetime.datetime.now()
        update_log.save()
        UpdateDefinition.objects \
                        .filter(slug=update_log.update_definition.slug) \
                        .update(status='active', last_started=update_log.started)

        try:
            yield
        finally:
            update_log.completed = datetime.datetime.now()
            update_log.save()
            UpdateDefinition.objects \
                            .filter(slug=update_log.update_definition.slug) \
                            .update(status='idle', last_completed=update_log.completed)

    def process_item(self, client, update_log):

        update_directory = tempfile.mkdtemp()
        try:

            graphs_touched = set()
            log = []

            variables = update_log.update_definition.variables.all()
            variables = dict((v.name, v.value) for v in variables)

            for pipeline in update_log.update_definition.pipelines.all():
                output_directory = tempfile.mkdtemp()
                transform_manager = TransformManager(update_log, output_directory, variables, force=update_log.forced)

                try:
                    pipeline = evaluate_pipeline(pipeline.value.strip())
                except SyntaxError:
                    raise ValueError("Couldn't parse the given pipeline: %r" % pipeline.text.strip())

                try:
                    pipeline(transform_manager)
                except NotChanged:
                    logger.info("Aborted update as data hasn't changed")
                except TransformException, e:
                    transform_manager.logger.exception("Transform failed.")
                finally:
                    shutil.rmtree(output_directory)

                log.append(transform_manager.log_stream.getvalue())
                graphs_touched |= transform_manager.graphs_touched

            updated = self.time_zone.localize(datetime.datetime.now())
            
            update_log.log = '\n\n'.join(log)

            client.publish(self.UPDATED_CHANNEL,
                           self.pack({'slug': update_log.update_definition.slug,
                                      'graphs': graphs_touched,
                                      'updated': updated}))
        finally:
            shutil.rmtree(update_directory)
