import base64
import datetime
import os
import pickle

import redis
from django.conf import settings

class TransformManager(object):
    def __init__(self, config_directory, output_directory, parameters):
        self.config_directory = config_directory
        self.output_directory = output_directory
        self.parameters = parameters
        self.counter = 0
        self.transforms = []
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

class Transform(object):
    # A mapping from file extensions to rdflib formats.
    rdf_formats = {
        'rdf': 'xml',
        'n3': 'n3',
        'ttl': 'n3',
        'nt': 'nt',
    }
    
    def __or__(self, other):
        if isinstance(other, type) and issubclass(other, Transform):
            other = other()
        if not isinstance(other, Transform):
            raise AssertionError('%r must be a Transform' % other)
        
        return Chain(self, other)
    
    def __call__(self, transform_manager):
        return self.execute(transform_manager)
    
    def execute(self, update_manager):
        raise NotImplementedError
        

class Chain(Transform):
    def __init__(self, first, second):
        self._first, self._second = first, second
    
    def execute(self, transform_manager, *args):
        return self._second.execute(transform_manager,
                                    self._first.execute(transform_manager, *args))
