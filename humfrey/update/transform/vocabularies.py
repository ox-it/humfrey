import shutil
import urllib2

from django.conf import settings
import rdflib

from humfrey.utils.namespaces import NS
from humfrey.update.transform.base import Transform
from humfrey.update.transform.upload import Upload

class VocabularyLoader(Transform):
    def execute(self, transform_manager):
        for prefix, uri in NS.iteritems():
            self.load_vocabulary(transform_manager, prefix, uri)

    def load_vocabulary(self, transform_manager, prefix, uri):
        overrides = getattr(settings, 'VOCABULARY_URL_OVERRIDES', {})
        uri = overrides.get(prefix, uri)
        if not uri:
            return

        request = urllib2.Request(uri)
        request.headers['Accept'] = 'application/rdf+xml, text/n3'

        try:
            response = urllib2.urlopen(request)
        except (urllib2.URLError, urllib2.HTTPError):
            transform_manager.logger.exception("Failed to retrieve %r for vocabulary %r", uri, prefix)
            return
        content_type = response.headers['Content-type'].split(';')[0]
        if content_type == 'application/rdf+xml':
            extension = 'rdf'
        elif content_type in ('text/n3', 'text/plain', 'text/turtle'):
            extension = 'ttl'
        else:
            transform_manager.logger.exception('Unexpected content-type: %r', content_type)
            return

        with open(transform_manager(extension), 'w') as output:
            shutil.copyfileobj(response, output)

        graph_name = settings.GRAPH_BASE + 'vocabulary/' + prefix
        upload = Upload(graph_name)
        upload.execute(transform_manager, output.name)
