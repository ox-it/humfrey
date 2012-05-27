import httplib2
import logging
import socket
import urlparse

from celery.task import task
from django.conf import settings
from django.db.models import Q

from humfrey.update.uploader import Uploader
from . import extraction, models

logger = logging.getLogger(__name__)

download_cache = getattr(settings, 'DOWNLOAD_CACHE', None)

@task(name='humfrey.pingback.process_new_pingback')
def process_new_pingback(pingback):
    source_url = urlparse.urlparse(pingback.source)
    source_domain = source_url.netloc.split(':')[0].lower()

    target_url = urlparse.urlparse(pingback.target)
    target_domain = target_url.netloc.split(':')[0].lower()

    if target_domain not in settings.PINGBACK_TARGET_DOMAINS:
        logger.warning('Pingback for non-targetable host: %r (%r)' % (target_domain, pingback.target))
        pingback.mark_invalid('non-targetable-host')
        return
    if source_url.scheme not in ('http', 'https', 'ftp'):
        logger.warning('Unsupported scheme for pingback')
        pingback.mark_invalid('unsupported-source-scheme')
        return

    pingback.state = 'processing'
    pingback.save()
    
    try:
        http = httplib2.Http(download_cache)
        response = http.request(uri=pingback.source,
                                headers={'Accept': 'application/rdf+xml, text/n3, text/turtle, application/xhtml+xml;q=0.9, text/html;q=0.8'})
    except httplib2.HttpLib2Error:
        logger.warning("Failed to retrieve pingback source: %s", pingback.source, exc_info=True)
        pingback.mark_invalid('http-error')
        return

        try:
            graph = extraction.extract(pingback, response)
        except extraction.InvalidPingback, e:
            pingback.mark_invalid(e.reason)
        else:
            pingback.invalid_reason = ''
            pingback.data = graph.serialize(format='n3')

            try:
                hostname = socket.gethostbyaddr(pingback.remote_addr)[0]
            except Exception:
                hostname = None

            source_domain = urlparse.urlparse(pingback.source)[1]

            actions = models.AutomatedAction.objects.filter(Q(field='ip', value=pingback.remote_addr) |
                                                            Q(field='hostname', value=hostname) |
                                                            Q(field='domain', value=source_domain)).order_by('action')

            for action in actions:
                if action.action == 'accepted':
                    pingback.accept()
                    break
                elif action.action == 'rejected':
                    pingback.reject()
                    break
            else:
                pingback.mark_pending()

@task(name='humfrey.pingback.accept_pingback')
def accept_pingback(pingback):
    uploader = Uploader()
    uploader.upload(store=pingback.store,
                    graph_name=pingback.graph_name,
                    data=pingback.data,
                    mimetype='text/n3')

    pingback.mark_published()
