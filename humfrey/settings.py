# coding=utf-8

# Django settings for humfrey project.
import os

import rdflib

DEBUG = os.environ.get('DJANGO_DEBUG') in ('on', 'yes')
TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split() if not DEBUG else ['*']

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
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if DEBUG and not SECRET_KEY:
    SECRET_KEY = 'debug secret key'
elif not SECRET_KEY:
    raise RuntimeError("You need to specify a DJANGO_SECRET_KEY environment variable.")

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django_hosts.middleware.HostsRequestMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'humfrey.base.middleware.AccessControlAllowOriginMiddleware',
    'django_hosts.middleware.HostsResponseMiddleware',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django_hosts',
    'django_conneg',
    'django_celery_beat',
    'guardian',
    'humfrey.base',
    'humfrey.desc',
    'humfrey.linkeddata',
    'humfrey.results',
    'humfrey.sparql',
    'humfrey.streaming',
    'humfrey.thumbnail',
    'humfrey.utils',
    # Uncomment the next line to enable the admin:
    # 'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': []
        }
    },
]

django_templates_options = TEMPLATES[0]['OPTIONS']

IMAGE_TYPES = ('foaf:Image',)
IMAGE_PROPERTIES = ('foaf:depiction',)

# Pull e-mail configuration from config file.
EMAIL_HOST = os.environ.get('SMTP_SERVER')
DEFAULT_FROM_EMAIL = os.environ.get('DJANGO_DEFAULT_FROM_EMAIL', 'webmaster@localhost')
SERVER_EMAIL = os.environ.get('DJANGO_SERVER_EMAIL', 'root@localhost')
EMAIL_SUBJECT_PREFIX = '[humfrey] '

CACHE_BACKEND = os.environ.get('DJANGO_CACHE_BACKEND', 'locmem://')

# Cache directories

CACHE_DIRECTORY = os.environ.get('HUMFREY_CACHE_DIRECTORY', os.path.expanduser('~/.humfrey/cache/'))
IMAGE_CACHE_DIRECTORY = os.environ.get('HUMFREY_IMAGE_CACHE_DIRECTORY', os.path.expanduser('~/.humfrey/images/'))
UPDATE_CACHE_DIRECTORY = os.environ.get('HUMFREY_UPDATE_CACHE_DIRECTORY', os.path.expanduser('~/.humfrey/update/'))
DOWNLOADER_DEFAULT_DIR = os.environ.get('HUMFREY_DOWNLOAD_DIRECTORY', os.path.expanduser('~/.humfrey/download/'))

REDIS_PARAMS = {'host': os.environ.get('REDIS_HOST') or 'localhost',
                'port': int(os.environ.get('REDIS_PORT', 6379)),
                'db': int(os.environ.get('REDIS_DB', 0))}

# These will be linked directly, others will be described using /doc/?uri=… syntax.
SERVED_DOMAINS = ()

ID_MAPPING = ()
ADDITIONAL_NAMESPACES = {}

if 'GOOGLE_ANALYTICS_KEY' in os.environ:
    INSTALLED_APPS += ('humfrey.analytics',)
    django_templates_options['context_processors'].append('humfrey.analytics.context_processors.google_analytics')
    GOOGLE_ANALYTICS = {
        'key': os.environ['GOOGLE_ANALYTICS_KEY'],
        'zero_timeouts': os.environ.get('GOOGLE_ANALYTICS_ZERO_TIMEOUTS') in ('on' ,'yes', 'true'),
    }

DOC_RDF_PROCESSORS = (
    'humfrey.desc.rdf_processors.doc_meta',
    'humfrey.desc.rdf_processors.formats',
)

# Load pingback functionality if specified in the config.
if os.environ.get('HUMFREY_PINGBACK_DATASET'):
    MIDDLEWARE_CLASSES += ('humfrey.pingback.middleware.PingbackMiddleware',)
    INSTALLED_APPS += ('humfrey.pingback',)
    DOC_RDF_PROCESSORS += ('humfrey.pingback.rdf_processors.pingback',)
    PINGBACK_TARGET_DOMAINS = os.environ.get('HUMFREY_PINGBACK_TARGET_DOMAINS', '').split()
    PINGBACK_DATASET = rdflib.URIRef(os.environ['HUMFREY_PINGBACK_DATASET'])

if os.environ.get('HUMFREY_UPDATES_ENABLED') in ('on' ,'yes', 'true'):
    INSTALLED_APPS += ('humfrey.update',)
    UPDATE_TRANSFORMS = (
        'humfrey.update.transform.base.Requires',
        'humfrey.update.transform.construct.Construct',
        'humfrey.update.transform.html.HTMLToXML',
        'humfrey.update.transform.local_file.LocalFile',
        'humfrey.update.transform.normalize.Normalize',
        'humfrey.update.transform.retrieve.Retrieve',
        'humfrey.update.transform.sharepoint.SharePoint',
        'humfrey.update.transform.shell.Shell',
        'humfrey.update.transform.spreadsheet.GnumericToTEI',
        'humfrey.update.transform.spreadsheet.ODSToTEI',
        'humfrey.update.transform.union.Union',
        'humfrey.update.transform.upload.Upload',
        'humfrey.update.transform.vocabularies.VocabularyLoader',
        'humfrey.update.transform.xslt.XSLT',
    )

if os.environ.get('HUMFREY_CKAN_API_KEY'):
    CKAN_API_KEY = os.environ['HUMFREY_CKAN_API_KEY']
    CKAN_GROUPS = set()
    CKAN_TAGS = set()


SPARQL_FORM_COMMON_PREFIXES = os.environ.get('HUMFREY_SPARQL_COMMON_PREFIXES', 'yes') in ('on' ,'yes', 'true')

GRAPH_BASE = os.environ.get('HUMFREY_GRAPH_BASE', 'http://localhost/graph/')
