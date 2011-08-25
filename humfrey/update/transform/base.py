import datetime
import os

class FileManager(object):
    def __init__(self, output_directory):
        self.output_directory = output_directory
        self.counter = 0
        self.transforms = []
    def __call__(self, extension):
        filename = os.path.join(self.output_directory, '%s.%s' % (self.counter, extension))
        self.counter += 1
        return filename
    def start(self, transform, inputs, outputs, type='generic'):
        self.current = {'transform': transform,
                        'inputs': inputs,
                        'outputs': outputs,
                        'start': datetime.datetime.now(),
                        'type': type}
    def end(self):
        self.current['end'] = datetime.datetime.now()
        self.transforms.append(self.current)
        del self.current

class Transform(object):
    def __or__(self, other):
        if isinstance(other, type) and issubclass(other, Transform):
            other = other()
        if not isinstance(other, Transform):
            raise AssertionError('%r must be a Transform' % other)
        
        return Chain(self, other)
    
    def __call__(self, output_directory):
        file_manager = FileManager(output_directory)
        return self.execute(file_manager)
    
    def execute(self, file_manager):
        raise NotImplementedError
        

class Chain(Transform):
    def __init__(self, first, second):
        self._first, self._second = first, second
    
    def execute(self, file_manager, *args):
        return self._second.execute(file_manager,
                                    self._first.execute(file_manager, *args))
