import logging
from optparse import make_option
import os
import sys
import threading
import time

import redis

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module

from humfrey.longliving.base import LonglivingThread

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    LOCK_NAME = 'longliving:lock'

    option_list = BaseCommand.option_list + (
        make_option('--log-level',
            action='store',
            dest='level',
            default=None,
            help='Log level'),
        )

    def get_threads(self, bail):
        try:
            longliving_classes = settings.LONGLIVING_CLASSES
        except AttributeError:
            raise ImproperlyConfigured("LONGLIVING_CLASSES setting missing.")

        threads = []
        for class_path in longliving_classes:
            module_name, class_name = class_path.rsplit('.', 1)
            try:
                module = import_module(module_name)
            except ImportError:
                raise ImproperlyConfigured("Could not import module %r" % module_name)
            try:
                cls = getattr(module, class_name)
            except AttributeError:
                raise ImproperlyConfigured("Module %r has no attribute %r" % (module_name, class_name))
            if not issubclass(cls, threading.Thread):
                raise ImproperlyConfigured("%r must be a subclass of threading.Thread" % class_path)
            thread = cls(bail)
            thread.name = class_path
            threads.append(thread)
        return threads

    def handle_noargs(self, *args, **options):
        log_level = options.pop('level', None)
        if log_level:
            logging.basicConfig(stream=sys.stderr, level=getattr(logging, log_level.upper()))

        redis_client = redis.client.Redis(**settings.REDIS_PARAMS)

        existing_pid = redis_client.get(self.LOCK_NAME)
        if not redis_client.setnx(self.LOCK_NAME, os.getpid()):
            existing_pid = int(redis_client.get(self.LOCK_NAME))
            try:
                os.kill(existing_pid, 0)
            except OSError:
                redis_client.set(self.LOCK_NAME, os.getpid())
            else:
                logger.warning("Not starting as another instance detected.")
                sys.stderr.write("Already running\n")
                sys.exit(1)
        logger.info("Starting longliving process")

        try:
            bail = threading.Event()
            threads = self.get_threads(bail)

            for thread in threads:
                thread.start()

            logger.info("Longliving threads started")

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Caught KeyboardInterrupt; shutting down.")
                bail.set()
                redis_client.publish(LonglivingThread.BAIL_CHANNEL, '')

            for i in range(5):
                for thread in threads[:]:
                    thread.join(5)
                    if thread.isAlive():
                        logger.warning("Couldn't join thread %r on attempt %i/5", thread.name, i + 1)
                    else:
                        threads.remove(thread)

            if threads:
                logger.error("Couldn't join all threads.")
            else:
                logger.info("All threads finished; stopping.")
        finally:
            redis_client.delete(self.LOCK_NAME)
