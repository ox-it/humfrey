# coding=utf-8

# Django settings for humfrey project.
import ConfigParser
import os

import rdflib

from django.conf.global_settings import TEMPLATE_CONTEXT_PROCESSORS

try:
    HUMFREY_CONFIG_FILE = os.environ['HUMFREY_CONFIG_FILE']
except KeyError:
    raise RuntimeError('You need to provide a HUMFREY_CONFIG_FILE environment variable pointing to an ini file')

config = ConfigParser.ConfigParser()
config.read(HUMFREY_CONFIG_FILE)

def relative_path(*args):
    # Return None if any of the arguments are None.
    if all(args):
        return os.path.abspath(os.path.join(os.path.dirname(HUMFREY_CONFIG_FILE), *args))

config = dict((':'.join([sec, key]), config.get(sec, key)) for sec in config.sections() for key in config.options(sec))

DEBUG = config.get('main:debug') == 'true'
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

#DATABASES = type('NonZeroDict', (dict,), {'__nonzero__': lambda self:True, '__contains__': lambda self, item: True})()

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/London'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-gb'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# Make this unique, and don't share it with anybody.
SECRET_KEY = config.get('main:secret_key')
if not SECRET_KEY:
    raise RuntimeError("You need to specify a secret_key in your config.ini.")

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django_hosts.middleware.HostsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'humfrey.base.middleware.AccessControlAllowOriginMiddleware',
)

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django_hosts',
    'django_conneg',
    'object_permissions',
    'humfrey.base',
    'humfrey.desc',
    'humfrey.linkeddata',
    'humfrey.sparql',
    'humfrey.results',
    # Uncomment the next line to enable the admin:
    # 'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
)

LONGLIVING_CLASSES = set([
    'django_longliving.longliving.pubsub.PubSubDispatcherThread',
])

LONGLIVING_PUBSUB_WATCHERS = ('humfrey.archive.pubsub.update_dataset_archives',)

IMAGE_TYPES = ('foaf:Image',)
IMAGE_PROPERTIES = ('foaf:depiction',)

# Pull e-mail configuration from config file.
EMAIL_HOST = config.get('email:host')
EMAIL_PORT = int(config.get('email:port') or 0) or None
EMAIL_HOST_USER = config.get('email:user')
EMAIL_HOST_PASSWORD = config.get('email:password')
SERVER_EMAIL = config.get('email:server_email_address')
DEFAULT_FROM_EMAIL = config.get('email:default_from_email_address')

# Endpoint details
ENDPOINT_QUERY = config.get('endpoints:query')
ENDPOINT_UPDATE = config.get('endpoints:update')
ENDPOINT_GRAPH = config.get('endpoints:graph')

CACHE_BACKEND = config.get('supporting_services:cache_backend') or 'locmem://'

# Cache directories

CACHE_DIRECTORY = relative_path(config.get('main:cache_directory'))
IMAGE_CACHE_DIRECTORY = relative_path(config.get('images:cache_directory')) \
                     or (CACHE_DIRECTORY and os.path.join(CACHE_DIRECTORY, 'images'))
UPDATE_CACHE_DIRECTORY = relative_path(config.get('update:cache_directory')) \
                     or (CACHE_DIRECTORY and os.path.join(CACHE_DIRECTORY, 'update'))

REDIS_PARAMS = {'host': config.get('supporting_services:redis_host') or 'localhost',
                'port': int(config.get('supporting_services:redis_port') or 6379),
                'db': int(config.get('supporting_services:redis_db') or 0)}

REDIS_PARAMS = {} if config.get('supporting_services:disable_redis_support') == 'true' else REDIS_PARAMS

# These will be linked directly, others will be described using /doc/?uri=… syntax.
SERVED_DOMAINS = ()

ID_MAPPING = ()
ADDITIONAL_NAMESPACES = {}

THUMBNAIL_WIDTHS = tuple(int(w.strip()) for w in config.get('images:thumbnail_widths', '200').split(','))
THUMBNAIL_HEIGHTS = tuple(int(w.strip()) for w in config.get('images:thumbnail_heights', '200').split(','))

DOWNLOADER_DEFAULT_DIR = config.get('downloader:default_dir')
if DOWNLOADER_DEFAULT_DIR:
    DOWNLOADER_DEFAULT_DIR = relative_path(DOWNLOADER_DEFAULT_DIR)

LOG_FILENAMES = {}
for k in ('access', 'pingback', 'query'):
    v = config.get('logging:%s' % k, None)
    if v:
        v = relative_path(v)
    LOG_FILENAMES[k] = v
del k, v

if config.get('main:log_to_stderr') == 'true':
    import logging
    import sys
    log_level = config.get('main:log_level') or 'WARNING'
    if log_level not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        raise RuntimeError('log_level in config file must be one of DEBUG, INFO, WARNING, ERROR and CRITICAL')
    logging.basicConfig(stream=sys.stderr,
                        level=getattr(logging, log_level))

if config.get('google_analytics:key'):
    INSTALLED_APPS += ('humfrey.analytics',)
    TEMPLATE_CONTEXT_PROCESSORS += ('humfrey.analytics.context_processors.google_analytics',)
    GOOGLE_ANALYTICS = {
        'key': config['google_analytics:key'],
        'zero_timeouts': config.get('google_analytics:zero_timeouts') == 'true',
    }

DOC_RDF_PROCESSORS = (
    'humfrey.desc.rdf_processors.doc_meta',
    'humfrey.desc.rdf_processors.formats',
)

# Load pingback functionality if specified in the config.
if config.get('pingback:enabled') == 'true':
    MIDDLEWARE_CLASSES += ('humfrey.pingback.middleware.PingbackMiddleware',)
    INSTALLED_APPS += ('humfrey.pingback', 'django_longliving')
    DOC_RDF_PROCESSORS += ('humfrey.pingback.rdf_processors.pingback',)
    LONGLIVING_CLASSES |= set(['humfrey.pingback.longliving.pingback_server.PingbackServer',
                               'humfrey.update.longliving.downloader.Downloader',
                               'humfrey.update.longliving.uploader.Uploader',
                               ])
    PINGBACK_TARGET_DOMAINS = (config.get('pingback:target_domains') or '').split()
    PINGBACK_DATASET = rdflib.URIRef(config['pingback:dataset'])

if config.get('update:enabled') == 'true':
    INSTALLED_APPS += ('humfrey.update',)
    LONGLIVING_CLASSES |= set(['humfrey.update.longliving.updater.Updater'])
    UPDATE_TRANSFORMS = (
        'humfrey.update.transform.html.HTMLToXML',
        'humfrey.update.transform.local_file.LocalFile',
        'humfrey.update.transform.retrieve.Retrieve',
        'humfrey.update.transform.spreadsheet.GnumericToTEI',
        'humfrey.update.transform.spreadsheet.ODSToTEI',
        'humfrey.update.transform.union.Union',
        'humfrey.update.transform.upload.Upload',
        'humfrey.update.transform.vocabularies.VocabularyLoader',
        'humfrey.update.transform.xslt.XSLT',
    )
    UPDATE_TRANSFORM_REPOSITORY = config.get('update:transform_repository')

if config.get('ckan:enabled') == 'true':
    LONGLIVING_PUBSUB_WATCHERS += ('humfrey.ckan.pubsub.update_ckan_dataset',)
    CKAN_API_KEY = config.get('ckan:api_key')
    CKAN_GROUPS = set()
    CKAN_TAGS = set()


SPARQL_FORM_COMMON_PREFIXES = (config.get('sparql:form_common_prefixes') or 'true') == 'true'

CACHE_TIMES = {
    'page': 1800,
}
CACHE_TIMES.update(dict((k[6:], int(v)) for k, v in config.iteritems() if k.startswith('cache:')))

GRAPH_BASE = config.get('main:graph_base') or 'http://localhost/graph/'
