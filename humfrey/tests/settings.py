import os

os.environ['HUMFREY_CONFIG_FILE'] = os.path.join(os.path.dirname(__file__), '..', 'tests', 'data', 'config.ini')

from humfrey.settings.common import *

ROOT_HOSTCONF = 'humfrey.tests.hosts'
DEFAULT_HOST = 'empty'
ROOT_URLCONF = 'humfrey.tests.urls.empty'
