import sys
import threading
import time

import redis

from django.core.management.base import NoArgsCommand
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured 
from django.utils.importlib import import_module

class Command(NoArgsCommand):
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
            threads.append(cls(bail))
        return threads
    
    def handle_noargs(self, **options):
        redis_client = redis.client.Redis(**settings.REDIS_PARAMS)
        
        if not redis_client.setnx('longliving:lock', 1):
            sys.stderr.write("Already running\n")
            sys.exit(1)
        
        try:
            bail = threading.Event()
            threads = self.get_threads(bail)
        
            for thread in threads:
                thread.start()
        
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                bail.set()
            
            for thread in threads:
                thread.join()
        finally:
            redis_client.delete('longliving:lock')
        
        
        

