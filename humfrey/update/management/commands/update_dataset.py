import base64
import datetime
import os
import pickle

from lxml import etree
import redis

from django.core.management.base import BaseCommand
from django.conf import settings

from humfrey.update.longliving.updater import Updater

class Command(BaseCommand):
    def handle(self, *args, **options):
        config_filename = os.path.abspath(args[0])
        trigger = args[1] if len(args) > 1 else 'manual'
        
        with open(config_filename, 'r') as f:
            config_file = etree.parse(f)
        
        dataset_name = config_file.xpath('meta/name')[0].text
        
        client = redis.client.Redis(**settings.REDIS_PARAMS)
        
        client.rpush(Updater.QUEUE_NAME, base64.b64encode(pickle.dumps({
            'config_filename': config_filename,
            'name': dataset_name,
            'trigger': trigger,
            'queued_at': datetime.datetime.now(),
        })))

if __name__ == '__main__':
    import sys
    Command().handle(*sys.argv[1:])