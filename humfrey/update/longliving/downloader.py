from __future__ import with_statement

import hashlib
import logging
import tempfile
import urllib2

from django.conf import settings

from django_longliving.base import LonglivingThread

logger = logging.getLogger(__name__)

class Downloader(LonglivingThread):
    QUEUE_NAME = 'downloader:queue'

    DEFAULT_USER_AGENT = 'Mozilla (compatible; Humfrey downloader; https://github.com/oucs/humfrey)'
    DEFAULT_ACCEPT = 'application/rdf+xml, text/n3, text/turtle, application/xhtml+xml;q=0.9, text/html;q=0.9'

    SAVE_BASE = settings.DOWNLOADER_DEFAULT_DIR or None

    def run(self):
        client = self.get_redis_client()

        for _, item in self.watch_queue(client, 'downloader:queue', True):
            try:
                self.download_item(client, item)
            except Exception:
                logger.exception('Failed to download item')
                failure_queue = item.get('failure_queue', 'downloader:failures')
                client.rpush(failure_queue, self.pack(item))

    def download_item(self, client, item):
        url_hash = hashlib.sha1(item['url']).hexdigest()

        headers = {
            'User-Agent': self.DEFAULT_USER_AGENT,
            'Accept': self.DEFAULT_ACCEPT,
        }
        if 'headers' in item:
            headers.update(item['headers'])
        if 'accept' in item:
            headers['Accept'] = item['accept']

        request = urllib2.Request(item['url'])
        for key, value in headers.iteritems():
            request.headers[key] = value

        target_queue = item['target_queue']
        failure_queue = item.get('failure_queue', target_queue)

        if item.get('conditional_caching'):
            etag = client.hget('downloader:etag', url_hash)
            last_modified = client.hget('downloader:last-modified', url_hash)

            if etag:
                headers['If-None-Match'] = etag
            if last_modified:
                headers['If-Modified-Since'] = last_modified

        response = None
        try:
            response = urllib2.urlopen(request)
        except urllib2.URLError, e:
            item['error'] = repr(e)
            logging.exception("Couldn't retrieve file")
        except urllib2.HTTPError, e:
            if e.code in (204, 304):
                response = e
            else:
                item['status_code'] = e.code
                item['error'] = repr(e)
                logging.exception("Couldn't retrieve file")

        if response and response.code in (200, 201):
            filename = item.get('filename')
            sha1 = hashlib.sha1()
            if not filename:
                target_file = tempfile.NamedTemporaryFile(dir=self.SAVE_BASE, delete=False)
                filename = item['filename'] = target_file.name
            else:
                target_file = open(filename, 'w+b')
            with target_file:
                while True:
                    chunk = response.read(4096)
                    if not chunk:
                        break
                    sha1.update(chunk)
                    target_file.write(chunk)
            item['sha1'] = sha1.hexdigest()


        if response:
            old_sha1 = client.hget('downloader:sha1', url_hash)
            new_sha1 = item.get('sha1')

            item['status_code'] = response.code
            item['final_url'] = response.url
            item['headers'] = dict(response.headers)

            item['state'] = 'changed' if old_sha1 == new_sha1 else 'unchanged'

            if response.headers.get('ETag'):
                client.hset('downloader:etags', url_hash, response.headers['ETag'])
            if response.headers.get('Last-Modified'):
                client.hset('downloader:etags', url_hash, response.headers['Last-Modified'])

            client.lpush(target_queue, self.pack(item))
        else:
            item['state'] = 'error'
            client.lpush(failure_queue, self.pack(item))
