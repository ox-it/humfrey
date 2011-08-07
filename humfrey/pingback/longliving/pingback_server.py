import datetime
import logging
import os
import socket
import urlparse

from lxml import etree
import rdflib

from django.conf import settings

from humfrey.longliving.base import LonglivingThread
from humfrey.longliving.longliving.downloader import Downloader
from humfrey.update.longliving.updater import Updater
from humfrey.utils.namespaces import NS


logger = logging.getLogger('humfrey.pingback.server')

def set_expiry(client, ping_hash):
    client.expire('pingback:item:%s' % ping_hash, 3600 * 24 * 7)

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
    QUEUE_NAME = 'pingback:new'

    ACCEPT_HEADER = 'application/rdf+xml, text/n3, text/turtle, application/xhtml+xml;q=0.9; text/html;q=0.8'
    def run(self):
        print "STARTING"
        client = self.get_redis_client()
        
        for _, ping_hash in self.watch_queue(client, self.QUEUE_NAME):
            print "HERE"
            item = self.unpack(client.get('pingback:item:%s' % ping_hash))
            self.process_item(client, ping_hash, item)
             
    def process_item(self, client, ping_hash, item):
        source_url = urlparse.urlparse(item['source'])
        source_domain = source_url.netloc.split(':')[0].lower()
        
        target_url = urlparse.urlparse(item['target'])
        target_domain = target_url.netloc.split(':')[0].lower()
        
        item['source_domain'] = source_domain
        item['target_domain'] = target_domain
        
        if target_domain not in settings.PINGBACK_TARGET_DOMAINS:
            logger.warning('Pingback for non-targetable host: %r (%r)' % (target_domain, item['target']))
            set_expiry(client, ping_hash)
            return
        if source_url.scheme not in ('http', 'https', 'ftp'):
            logger.warning('Unsupported scheme for pingback')
            set_expiry(client, ping_hash)
            return
        
        download_item = {
            'ping_hash': ping_hash,
            'url': item['source'],
            'target_queue': RetrievedPingbackHandler.QUEUE_NAME,
            'accept': self.ACCEPT_HEADER,
        }
        
        client.rpush(Downloader.QUEUE_NAME, self.pack(download_item))

class RetrievedPingbackHandler(LonglivingThread):
    QUEUE_NAME = 'pingback:retrieved'
    PENDING_QUEUE_NAME = 'pingback:pending'

    RDF_MEDIA_TYPES = {
        'application/rdf+xml': 'xml',
        'text/n3': 'n3',
        'text/turtle': 'n3',
    }

    def run(self):
        client = self.get_redis_client()
        
        for _, download_item in self.watch_queue(client, self.QUEUE_NAME, True):
            ping_hash = download_item['ping_hash']
            item = self.unpack(client.get('pingback:item:%s' % ping_hash))
            self.process_one(client, ping_hash, download_item, item)
    
    def process_one(self, client, ping_hash, download_item, item):
        self.process_two(client, ping_hash, download_item, item)
        client.set('pingback:item:%s' % ping_hash, item)
        
        filename = download_item.get('filename')
        if filename and os.path.exists(filename):
            os.unlink(filename)
        
        logging.info('Data with state %r' % item['state'])
        if item['state'] in ('invalid', 'rejected'):
            set_expiry(client, ping_hash)
        elif item['state'] == 'accepted':
            client.rpush(AcceptedPingbackHandler.QUEUE_NAME, ping_hash)
        elif item['state'] == 'pending':
            client.sadd(RetrievedPingbackHandler.PENDING_QUEUE_NAME, ping_hash)
        else:
            logging.error('Unexpected state')
        
    def process_two(self, client, ping_hash, download_item, item):
        source, target = (rdflib.URIRef(item[x]) for x in ('source', 'target'))

        content_type = download_item['headers'].get('content-type', '').split(';')[0].lower()
        
        graph, graph_metadata = rdflib.ConjunctiveGraph(), rdflib.ConjunctiveGraph()
        for prefix in NS:
            graph.namespace_manager.bind(prefix, NS[prefix])
            graph_metadata.namespace_manager.bind(prefix, NS[prefix])
        
        if content_type in ('application/xhtml+xml', 'text/html'):
            self.process_html(source, target, download_item['filename'], graph)
        elif content_type in self.RDF_MEDIA_TYPES:
            self.process_rdf(source, target, download_item['filename'], graph, self.RDF_MEDIA_TYPES[content_type])
        else:
            logger.warning('Unexpected media type for %r: %r' % (item['source'], content_type))
            item['state'] = 'invalid'
            return
    
        if not graph:
            item['state'] = 'invalid'
            return
        
        graph_name = rdflib.URIRef(settings.GRAPH_BASE + '/pingback/' + ping_hash)
    
        graph_metadata += (
            (graph_name, NS['dcterms'].created, rdflib.Literal(item['date'])),
            (graph_name, NS['dcterms'].source, rdflib.URIRef(download_item['final_url'])),
            (graph_name, NS['void'].inDataset, rdflib.URIRef('http://data.ox.ac.uk/id/dataset/pingbacks')),
            (graph_name, NS['dcterms']['title'], rdflib.Literal(u'Pingback from %s to %s' % (unicode(source), unicode(target)))),
        )
        
        item['graph'] = graph
        item['graph_metadata'] = graph_metadata
        item['graph_name'] = graph_name
        item['hostname'] = socket.gethostbyaddr(item['remote_addr'])[0]
        
        if client.sismember('pingback:whitelist:ip', item['remote_addr']) or \
           client.sismember('pingback:whitelist:hostname', item['hostname']) or \
           client.sismember('pingback:whitelist:source_domain', item['source_domain']):
            item['state'] = 'accepted'
        elif client.sismember('pingback:blacklist:ip', item['remote_addr']) or \
             client.sismember('pingback:blacklist:hostname', item['hostname']) or \
             client.sismember('pingback:blacklist:source_domain', item['source_domain']):
            item['state'] = 'rejected'
        else:
            item['state'] = 'pending'


    def process_html(self, source, target, filename, graph):
        with open(filename, 'r+b') as f:
            html = etree.parse(f, parser=etree.HTMLParser())
        
        for anchor in html.xpath(".//a"):
            if anchor.get('href') == str(target):
                break
        else:
            return
        
        graph.add((source, NS['sioc'].links_to, target))
            
        title = html.xpath('.//head/title')
        if title and title[0].text:
            graph.add((source, NS['dcterms']['title'], rdflib.Literal(title[0].text)))

class AcceptedPingbackHandler(LonglivingThread):
    QUEUE_NAME = 'pingback:accepted'
    def run(self):
        client = self.get_redis_client()
        for _, ping_hash in self.watch_queue(client, self.QUEUE_NAME):
            item = self.unpack('pingback:item:%s' % ping_hash)
            item['state'] = 'published'
            set_expiry(client, ping_hash)
            
            update_item = {
                'graph_name': item['graph_name'],
                'graph': item['graph'],
                'modified': datetime.datetime.now(),
            }
            
            client.rpush(Updater.QUEUE_NAME, self.pack(update_item))