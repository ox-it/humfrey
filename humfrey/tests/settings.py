import atexit

import os
import tempfile

os.environ['HUMFREY_CONFIG_FILE'] = os.path.join(os.path.dirname(__file__), 'data', 'config.ini')

from humfrey.settings import *

# Directory for variable files
VAR_DIR = tempfile.mkdtemp()

INSTALLED_APPS += (
    'humfrey.elasticsearch',
    'humfrey.archive',
    'humfrey.update',
)

def register_atexit(VAR_DIR):
    @atexit.register
    def remove_var_dir():
        import shutil
        shutil.rmtree(VAR_DIR)
register_atexit(VAR_DIR)


MEDIA_ROOT = os.path.join(VAR_DIR, 'media')
UPDATE_FILES_DIRECTORY = os.path.join(MEDIA_ROOT, 'update-files')

ROOT_HOSTCONF = 'humfrey.tests.hosts'
DEFAULT_HOST = 'empty'
ROOT_URLCONF = 'humfrey.tests.urls.empty'

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3'}}


TEST_URI = 'http://data/example.com/id/Foo'
TEST_DOMAIN = 'data.example.org'

import logging, sys
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
