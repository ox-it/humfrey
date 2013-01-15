from django.conf import settings
from humfrey import __version__, source_homepage

USER_AGENTS = {'agent': 'humfrey/{0} ({1}; {2})'.format(__version__, source_homepage, settings.DEFAULT_FROM_EMAIL),
               'browser': 'Mozilla (compatible; humfrey/{0}; {1}; {2})'.format(__version__, source_homepage, settings.DEFAULT_FROM_EMAIL)}
