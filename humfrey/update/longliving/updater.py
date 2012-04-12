import base64
import contextlib
import datetime
import functools
import logging
import os
import pickle
import tempfile
import thread
import traceback

import pytz

from django.conf import settings

from django_longliving.base import LonglivingThread
from humfrey.update.models import UpdateDefinition
from humfrey.update.transform.base import NotChanged, TransformException
from humfrey.update.utils import evaluate_pipeline

logger = logging.getLogger(__name__)

class _SameThreadFilter(logging.Filter):
    def __init__(self):
        self.thread_ident = thread.get_ident()
    def filter(self, record):
        return record.thread == self.thread_ident

class _TransformHandler(logging.Handler):
    ignore_loggers = frozenset(['django.db.backends'])

    def __init__(self, update_log):
        self.records = []
        self.ignore = False
        self.update_log = update_log
        logging.Handler.__init__(self)
        self.setLevel(0)

    def emit(self, record):
        if self.ignore or record.name in self.ignore_loggers:
            return
        record = dict(record.__dict__)
        if record.get('exc_info'):
            exc_info = record['exc_info']
            record['exc_info'] = exc_info[:2] + (traceback.format_tb(exc_info[2]),)
        previous = self.update_log.max_log_level
        if not previous or record['levelno'] > previous:
            self.update_log.max_log_level = record['levelno']
        record['time'] = pytz.utc.localize(datetime.datetime.utcnow()).astimezone(pytz.timezone(settings.TIME_ZONE))

        try:
            pickle.dumps(record)
        except Exception:
            for key in record.keys():
                try:
                    pickle.dumps(record[key])
                except Exception:
                    del record[key]

        self.records.append(record)

        # Ignore all log messages while attempting to save.
        self.ignore = True
        try:
            self.update_log.log = base64.b64encode(pickle.dumps(self.records))
            self.update_log.save()
        finally:
            self.ignore = False

class TransformManager(object):
    def __init__(self, update_log, output_directory, parameters, force=False):
        self.update_log = update_log
        self.owner = update_log.update_definition.owner
        self.output_directory = output_directory
        self.parameters = parameters
        self.force = force

        self.counter = 0
        self.transforms = []
        self.graphs_touched = set()

    def __call__(self, extension=None, name=None):
        if not name:
            name = '%s.%s' % (self.counter, extension)
            self.counter += 1
        filename = os.path.join(self.output_directory, name)
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

        logger = logging.getLogger()
        handler = _TransformHandler(update_log)
        handler.addFilter(_SameThreadFilter())

        UpdateDefinition.objects \
                        .filter(slug=update_log.update_definition.slug) \
                        .update(status='active', last_started=update_log.started)

        logger.addHandler(handler)
        try:
            yield
        finally:
            logger.removeHandler(handler)
            update_log.completed = datetime.datetime.now()
            update_log.save()
            UpdateDefinition.objects \
                            .filter(slug=update_log.update_definition.slug) \
                            .update(status='idle', last_completed=update_log.completed)

    def process_item(self, client, update_log):
        graphs_touched = set()

        variables = update_log.update_definition.variables.all()
        variables = dict((v.name, v.value) for v in variables)

        for pipeline in update_log.update_definition.pipelines.all():
            output_directory = tempfile.mkdtemp()
            transform_manager = TransformManager(update_log,
                                                 output_directory,
                                                 variables,
                                                 force=update_log.forced)

            try:
                pipeline = evaluate_pipeline(pipeline.value.strip())
            except SyntaxError:
                raise ValueError("Couldn't parse the given pipeline: %r" % pipeline.text.strip())

            try:
                pipeline(transform_manager)
            except NotChanged:
                logger.info("Aborted update as data hasn't changed")
            except TransformException, e:
                logger.exception("Transform failed.")
            except Exception, e:
                logger.exception("Transform failed, perhaps ungracefully.")
            finally:
                pass #shutil.rmtree(output_directory)

            graphs_touched |= transform_manager.graphs_touched

        updated = self.time_zone.localize(datetime.datetime.now())

        client.publish(self.UPDATED_CHANNEL,
                       self.pack({'slug': update_log.update_definition.slug,
                                  'graphs': graphs_touched,
                                  'updated': updated}))
