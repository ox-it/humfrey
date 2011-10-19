import logging
import os
import traceback
import urllib
import urllib2

from django.conf import settings

from humfrey.longliving.base import LonglivingThread

logger = logging.getLogger(__name__)

class Uploader(LonglivingThread):
    QUEUE_NAME = 'humfrey:uploader:queue'
    UPLOADED_PUBSUB = 'humfrey:uploader:uploaded-channel'

    def run(self):
        client = self.get_redis_client()

        for _, item in self.watch_queue(client, self.QUEUE_NAME, True):
            self.process_item(client, item)

    def process_item(self, client, item):
        graph_url = '%s?%s' % (settings.ENDPOINT_GRAPH,
                               urllib.urlencode({'graph': item['graph_name']}))

        if 'filename' in item:
            data = open(item['filename']).read()
        elif 'graph' in item:
            data = item['graph'].serialize()
        elif 'data' in item:
            data = item['data']

        request = urllib2.Request(graph_url, data)
        request.headers['Content-type'] = item.get('mimetype', 'text/plain')
        request.get_method = lambda: item['method']

        try:
            urllib2.urlopen(request)
        except Exception, e:
            if isinstance(e, urllib2.HTTPError) and e.code in (201, 204):
                item['outcome'] = 'success'
            else:
                item.update({'outcome': 'error',
                             'error': repr(e),
                             'traceback': traceback.format_exc()})
                logger.exception("Upload failed. Code %r", getattr(e, 'code', None))
        else:
            item.update({
                'outcome': 'success',
            })

        if 'filename' in item and item.get('delete_after'):
            os.unlink(item['filename'])

        client.publish(self.UPLOADED_PUBSUB, self.pack(item))
