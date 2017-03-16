from celery import shared_task

import collections
import contextlib
import datetime
import logging
import os
import pickle
import shutil
import tempfile
import _thread
import traceback

import pytz

from django.conf import settings

from humfrey.update.models import UpdateDefinition, UpdateLogRecord, UpdateLog
from humfrey.update.transform.base import NotChanged, TransformException
from humfrey.update.utils import evaluate_pipeline
from humfrey.signals import graphs_updated, update_completed

logger = logging.getLogger(__name__)


class _SameThreadFilter(logging.Filter):
    def __init__(self):
        self.thread_ident = _thread.get_ident()
    def filter(self, record):
        return record.thread == self.thread_ident


class _TransformHandler(logging.Handler):
    ignore_loggers = frozenset(['django.db.backends'])

    def __init__(self, update_log):
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
        previous = self.update_log.log_level
        if not previous or record['levelno'] > previous:
            self.update_log.log_level = record['levelno']
        record['time'] = pytz.utc.localize(datetime.datetime.utcnow()).astimezone(pytz.timezone(settings.TIME_ZONE))

        try:
            pickle.dumps(record)
        except Exception:
            for key in list(record.keys()):
                try:
                    pickle.dumps(record[key])
                except Exception:
                    del record[key]

        # Ignore all log messages while attempting to save.
        self.ignore = True
        try:
            update_log_record = UpdateLogRecord(update_log = self.update_log)
            update_log_record.record = record
            update_log_record.save()
        finally:
            self.ignore = False

class TransformManager(object):
    def __init__(self, update_log, output_directory, parameters, force, store_graphs, store):
        self.update_log = update_log
        self.owner = update_log.update_definition.owner
        self.output_directory = output_directory
        self.parameters = parameters
        self.force = force

        self.counter = 0
        self.transforms = []
        self.store_graphs = store_graphs
        self.store = store

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
        self.store_graphs[self.store].add(graph_name)
    def not_changed(self):
        if not self.force:
            raise NotChanged()

_time_zone = pytz.timezone(settings.TIME_ZONE)

@contextlib.contextmanager
def logged(update_log):
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
        update_log.log_level = update_log.log_level or 0
        update_log.save()
        UpdateDefinition.objects \
                        .filter(slug=update_log.update_definition.slug) \
                        .update(status='idle', last_completed=update_log.completed)


@shared_task(name='humfrey.update.update', ignore_result=True)
def update(update_log_id=None, slug=None, trigger=None):
    if slug:
        update_definition = UpdateDefinition.objects.get(slug=slug)
        update_definition.queue(silent=True, trigger=trigger)
        return
    elif not update_log_id:
        raise ValueError("One of update_log and slug needs to be provided.")

    update_log = UpdateLog.objects.get(id=update_log_id)
    
    # A mapping from Store to graph names
    store_graphs = collections.defaultdict(set)

    variables = update_log.update_definition.variables.all()
    variables = dict((v.name, v.value) for v in variables)

    with logged(update_log):
        for pipeline in update_log.update_definition.pipelines.all():
            for store in pipeline.stores.all():
                output_directory = tempfile.mkdtemp()
                transform_manager = TransformManager(update_log,
                                                     output_directory,
                                                     variables,
                                                     force=update_log.forced,
                                                     store_graphs=store_graphs,
                                                     store=store)
    
                try:
                    transform = evaluate_pipeline(pipeline.value.strip())
                except SyntaxError:
                    raise ValueError("Couldn't parse the given pipeline: %r" % pipeline.value.strip())
        
                try:
                    transform(transform_manager)
                except NotChanged:
                    logger.info("Aborted update as data hasn't changed")
                except TransformException:
                    logger.exception("Transform failed.")
                except Exception:
                    logger.exception("Transform failed, perhaps ungracefully.")
                finally:
                    shutil.rmtree(output_directory)

    updated = _time_zone.localize(datetime.datetime.now())
    
    store_graphs = {store.pk: sorted(store_graphs[store]) for store in store_graphs}

    for store_id in store_graphs:
        graphs_updated.send(update,
                            store_id=store_id,
                            graphs=store_graphs[store_id],
                            when=updated)

    update_completed.send(update,
                          update_definition_id=update_log.update_definition_id,
                          store_graphs=store_graphs,
                          when=updated)
