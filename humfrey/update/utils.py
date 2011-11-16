from django.conf import settings
from django.utils.importlib import import_module

from humfrey.update.transform.base import Transform

def get_transforms(self):
    try:
        return get_transforms._cache
    except AttributeError:
        pass

    transforms = {'__builtins__': {}}
    for class_path in settings.UPDATE_TRANSFORMS:
        module_path, class_name = class_path.rsplit('.', 1)
        transform = getattr(import_module(module_path), class_name)
        assert issubclass(transform, Transform)
        transforms[transform.__name__] = transform
        
    get_transforms._cache = transforms
    return transforms

def evaluate_pipeline(pipeline):
    return eval('(%s)' % pipeline, get_transforms())