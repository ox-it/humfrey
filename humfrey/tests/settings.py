import atexit
import imp
import os
import tempfile

os.environ['HUMFREY_CONFIG_FILE'] = os.path.join(os.path.dirname(__file__), 'data', 'config.ini')

from humfrey.settings.common import *

# Directory for variable files
VAR_DIR = tempfile.mkdtemp()

INSTALLED_APPS += (
    'humfrey.elasticsearch',
)

def register_atexit(VAR_DIR):
    @atexit.register
    def remove_var_dir():
        import shutil
        shutil.rmtree(VAR_DIR)
register_atexit(VAR_DIR)


MEDIA_ROOT = os.path.join(VAR_DIR, 'media')
UPDATE_FILES_DIRECTORY = os.path.join(MEDIA_ROOT, 'update-files')

# For object_permissions
TESTING = True

ROOT_HOSTCONF = 'humfrey.tests.hosts'
DEFAULT_HOST = 'empty'
ROOT_URLCONF = 'humfrey.tests.urls.empty'

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3'}}

TEST_RUNNER = 'humfrey.tests.runners.HumfreyTestSuiteRunner'

try:
    imp.find_module('django_jenkins')
except ImportError:
    pass
else:
    INSTALLED_APPS += ('django_jenkins',)

    JENKINS_TEST_RUNNER = 'humfrey.tests.runners.HumfreyJenkinsTestSuiteRunner'
    JENKINS_TASKS = ('django_jenkins.tasks.run_pylint',
                     'django_jenkins.tasks.with_coverage',
                     'django_jenkins.tasks.django_tests',
                     'django_jenkins.tasks.run_pep8',
                     'django_jenkins.tasks.run_pyflakes')

TEST_URI = 'http://data/example.com/id/Foo'
TEST_DOMAIN = 'data.example.org'

import logging, sys
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
