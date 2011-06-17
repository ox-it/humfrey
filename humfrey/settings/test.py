import os

os.environ['HUMFREY_CONFIG_FILE'] = os.path.join(os.path.dirname(__file__), '..', 'tests', 'data', 'config.ini')

from humfrey.settings.common import *
