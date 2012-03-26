import logging
import os
import traceback
import httplib
import tempfile
import urllib
import urllib2
import urlparse

from django.conf import settings

from django_longliving.base import LonglivingThread

from humfrey.sparql.models import Store

logger = logging.getLogger(__name__)

class Uploader(LonglivingThread):
    QUEUE_NAME = 'humfrey:uploader:queue'
    UPLOADED_PUBSUB = 'humfrey:uploader:uploaded-channel'

    def run(self):
        client = self.get_redis_client()

        for _, item in self.watch_queue(client, self.QUEUE_NAME, True):
            self.process_item(client, item)

    def process_item(self, client, item):
        if 'filename' in item:
            filename = item['filename']
        elif 'graph' in item:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                item['graph'].serialize(f, format='nt')
            filename = f.name
            item['delete_after'] = True
        elif 'data' in item:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(item['data'])
            filename = f.name
            item['delete_after'] = True

        for store in set(item['stores']):
            self.upload_to_store(item, filename, store)

        if item.get('delete_after'):
            os.unlink(filename)

        client.publish(self.UPLOADED_PUBSUB, self.pack(item))

    def upload_to_store(self, item, filename, store):
        if store is not None:
            graph_store_endpoint = Store.objects.get(slug=store).graph_store_endpoint
        else:
            graph_store_endpoint = settings.ENDPOINT_GRAPH

        graph_url = '%s?%s' % (graph_store_endpoint,
                               urllib.urlencode({'graph': item['graph_name']}))
        graph_url = urlparse.urlparse(graph_url)


        netloc = graph_url.netloc
        host, port = netloc.split(':')[0], int(netloc.split(':')[1]) if ':' in netloc else 80
        method = item.get('method', 'PUT')
        path = graph_url.path
        if graph_url.query:
            path += '?' + graph_url.query

        with open(filename, 'r') as f:

            conn = httplib.HTTPConnection(host=host, port=port)
            conn.connect()

            conn.putrequest(method, path)
            conn.putheader("User-Agent", "humfrey")
            conn.putheader("Content-Length", str(os.stat(filename).st_size))
            conn.putheader('Content-type', item.get('mimetype', 'text/plain'))
            conn.endheaders()

            conn.send(f)

            response = conn.getresponse()

            if response.status in (200, 201, 204):
                    item['outcome'] = 'success'
            else:
                item.update({'outcome': 'error',
                             'error': response.code,
                             'body': response.read()})
                logger.error("Upload failed. Code %r", response.status)

            conn.close()

