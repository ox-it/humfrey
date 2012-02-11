import imp
import os

os.environ['HUMFREY_CONFIG_FILE'] = os.path.join(os.path.dirname(__file__), 'data', 'config.ini')

from humfrey.settings.common import *

ROOT_HOSTCONF = 'humfrey.tests.hosts'
DEFAULT_HOST = 'empty'
ROOT_URLCONF = 'humfrey.tests.urls.empty'

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3'}}

try:
    imp.find_module('django_jenkins')
except ImportError:
    pass
else:
    INSTALLED_APPS += ('django_jenkins',)

    JENKINS_TEST_RUNNER = 'humfrey.tests.jenkins.HumfreyJenkinsTestSuiteRunner'
    JENKINS_TASKS = ('django_jenkins.tasks.run_pylint',
                     'django_jenkins.tasks.with_coverage',
                     'django_jenkins.tasks.django_tests',
                     'django_jenkins.tasks.run_pep8',
                     'django_jenkins.tasks.run_pyflakes')

TEST_URI = 'http://data/example.com/id/Foo'
TEST_DOMAIN = 'data.example.org'
