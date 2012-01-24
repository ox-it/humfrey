from __future__ import with_statement

import datetime
import logging
import os
import socket
import StringIO
import urlparse

from lxml import etree
import rdflib

from django.conf import settings
from django.db.models import Q
from django_longliving.base import LonglivingThread

from humfrey.update.longliving.downloader import Downloader
from humfrey.update.longliving.uploader import Uploader
from humfrey.utils.namespaces import NS

from humfrey.pingback import extraction
from humfrey.pingback.models import InboundPingback, AutomatedAction

logger = logging.getLogger(__name__)

class PingbackServer(LonglivingThread):

    LABEL_PREDICATES = (NS['rdfs'].label, NS['foaf'].name,
                        NS['dcterms']['title'], NS['dc']['title'])

    def run(self):
        handlers = [NewPingbackHandler(self._bail),
                    RetrievedPingbackHandler(self._bail),
                    AcceptedPingbackHandler(self._bail)]

        for handler in handlers:
            handler.start()
        for handler in handlers:
            handler.join()

class NewPingbackHandler(LonglivingThread):
    ACCEPT_HEADER = 'application/rdf+xml, text/n3, text/turtle, application/xhtml+xml;q=0.9, text/html;q=0.8'
    def run(self):
        client = self.get_redis_client()

        for _, slug in self.watch_queue(client, InboundPingback.PROCESS_QUEUE):
            try:
                pingback = InboundPingback.objects.get(slug=slug)
            except InboundPingback.DoesNotExist:
                logging.exception("Couldn't find pingback for slug %r", slug)
                continue
            self.process_item(client, pingback)

    def process_item(self, client, pingback):
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

        download_item = {
            'pingback': pingback,
            'url': pingback.source,
            'target_queue': RetrievedPingbackHandler.QUEUE_NAME,
            'accept': self.ACCEPT_HEADER,
        }

        client.rpush(Downloader.QUEUE_NAME, self.pack(download_item))

class RetrievedPingbackHandler(LonglivingThread):
    QUEUE_NAME = 'humfrey:pingback:inbound:retrieved-queue'

    def run(self):
        client = self.get_redis_client()

        for _, download_item in self.watch_queue(client, self.QUEUE_NAME, True):

            self.process(client, download_item['pingback'], download_item)

    def process(self, client, pingback, download_item):
        if download_item['state'] == 'error':
            pingback.mark_invalid('http-error')
            return

        pingback, url, filename, headers = map(download_item.get,
                                               ('pingback', 'final_url',
                                                'filename', 'headers'))

        try:
            graph = extraction.extract(pingback, url, filename, headers)
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

            actions = AutomatedAction.objects.filter(Q(field='ip', value=pingback.remote_addr) |
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

        finally:
            if filename and os.path.exists(filename):
                os.unlink(filename)


class AcceptedPingbackHandler(LonglivingThread):
    def run(self):
        client = self.get_redis_client()
        for _, slug in self.watch_queue(client, InboundPingback.ACCEPTED_QUEUE):
            try:
                pingback = InboundPingback.objects.get(slug=slug)
            except InboundPingback.DoesNotExist:
                logging.exception("Couldn't find pingback for slug %r", slug)
                continue

            graph = rdflib.ConjunctiveGraph()
            graph.parse(StringIO.StringIO(pingback.data), format='n3')

            update_item = {
                'graph_name': pingback.graph_name,
                'graph': graph,
                'modified': datetime.datetime.now(),
                'method': 'PUT',
            }

            client.rpush(Uploader.QUEUE_NAME, self.pack(update_item))

            pingback.mark_published()
