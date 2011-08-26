import os
import urllib
import urllib2

from django.conf import settings

from humfrey.longliving.base import LonglivingThread

class Uploader(LonglivingThread):
    QUEUE_NAME = 'updater:queue'
    UPLOADED_PUBSUB = 'updater:updated'

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
        request.headers['Content-Type'] = 'text/plain'
        request.get_method = item['method']
        
        try:
            urllib2.urlopen(request)
        except Exception, e:
            item.update({
                'outcome': 'error',
                'error': e,
            })
        else:
            item.update({
                'outcome': 'success',
            })
            
        if 'filename' in item and item.get('delete_after'):
            os.unlink(item['filename'])
        
        client.publish(self.UPLOADED_PUBSUB, self.pack(item))