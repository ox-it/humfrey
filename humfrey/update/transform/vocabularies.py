import httplib
import logging
import os
import shutil
import urllib2

from django.conf import settings
import rdflib

from humfrey.utils.namespaces import NS
from humfrey.update.transform.base import Transform
from humfrey.update.uploader import Uploader
from humfrey.update.tasks import retrieve

logger = logging.getLogger(__name__)

class VocabularyLoader(Transform):
    def execute(self, transform_manager):

        for prefix, uri in NS.iteritems():
            try:
                self.load_vocabulary(transform_manager, prefix, uri)
            except Exception, e:
                logger.exception("Failed to load vocabulary: %r from %r", prefix, uri)

    def load_vocabulary(self, transform_manager, prefix, uri):
        overrides = getattr(settings, 'VOCABULARY_URL_OVERRIDES', {})
        uri = overrides.get(prefix, uri)
        if not uri:
            return

        filename, headers = retrieve(uri)

        if not filename:
            logger.error("Unable to retrieve: %s", headers.get('message'))
            return

        try:

            logger.debug("About to fetch %r for vocabulary %r", uri, prefix)

            if headers['status'] != httplib.OK:
                logger.error("Failed to retrieve %r for vocabulary %r", uri, prefix, extra={'headers': headers})
                return
            content_type = headers['content-type'].split(';')[0]
            if content_type not in ('application/rdf+xml', 'text/n3', 'text/plain', 'text/turtle'):
                logger.error('Unexpected content-type: %r', content_type)
                return

            graph_name = settings.GRAPH_BASE + 'vocabulary/' + prefix
            Uploader.upload(stores=(transform_manager.store,),
                            graph_name=graph_name,
                            filename=filename,
                            mimetype=content_type)
        finally:
            if headers['delete-after']:
                os.unlink(filename)
