import os
import tempfile

import redis
from lxml import etree

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured 
from django.utils.importlib import import_module

from humfrey.update.transform.html import HTMLToXML
from humfrey.update.transform.local_file import LocalFile
from humfrey.update.transform.retrieve import Retrieve
from humfrey.update.transform.spreadsheet import GnumericToTEI, ODSToTEI
from humfrey.update.transform.upload import Upload
from humfrey.update.transform.xslt import XSLT


class Command(BaseCommand):
    transforms = (HTMLToXML, LocalFile, Retrieve, GnumericToTEI, ODSToTEI,
                  Upload, XSLT)
    transforms = dict((t.__name__, t) for t in transforms)
    transforms['__builtins__'] = {}
    
    def handle(self, *args, **options):
        config_file = etree.parse(args[0])
        
        if config_file.getroot().tag != 'update-definition':
            raise ValueError("This isn't an update definition")
        
        config_directory = os.path.abspath(os.path.dirname(args[0]))
        
        for pipeline in config_file.xpath('pipeline'):
            output_directory = tempfile.mkdtemp()
            
            pipeline = eval('(%s)' % pipeline.text.strip(), self.transforms)
            
            pipeline(config_directory, output_directory)
            
            
            print pipeline
        

