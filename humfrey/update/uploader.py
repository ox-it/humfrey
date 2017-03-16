import logging
import os
import http.client
import tempfile
import urllib.request
import urllib.error
import urllib.parse

from django.conf import settings

from humfrey.sparql.models import Store

logger = logging.getLogger(__name__)

class Uploader(object):
    @classmethod
    def upload(cls, stores, graph_name,
               filename=None, graph=None, data=None,
               delete_after=False, method='PUT', mimetype='text/plain'):
        if filename:
            pass
        elif graph:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                graph.serialize(f, format='nt')
            filename = f.name
            delete_after = True
        elif data:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(data)
            filename = f.name
            delete_after = True

        for store in set(stores):
            cls.upload_to_store(store, graph_name, method, filename, mimetype)

        if delete_after:
            os.unlink(filename)

    @classmethod
    def upload_to_store(cls, store, graph_name, method, filename, mimetype):
        if isinstance(store, Store):
            graph_store_endpoint = store.graph_store_endpoint
        elif isinstance(store, str):
            graph_store_endpoint = Store.objects.get(slug=store).graph_store_endpoint
        else:
            raise TypeError("store must be Store or basestring, not %r", type(store))

        graph_url = '%s?%s' % (graph_store_endpoint,
                               urllib.parse.urlencode({'graph': graph_name}))
        graph_url = urllib.parse.urlparse(graph_url)


        netloc = graph_url.netloc
        host, port = netloc.split(':')[0], int(netloc.split(':')[1]) if ':' in netloc else 80
        path = graph_url.path
        if graph_url.query:
            path += '?' + graph_url.query

        with open(filename, 'rb') as f:

            logger.debug("Opening connection to %s:%d", host, port)

            conn = http.client.HTTPConnection(host=host, port=port)
            conn.connect()

            logger.debug("Connected")

            conn.putrequest(method, path)
            conn.putheader("User-Agent", "humfrey")
            conn.putheader("Content-Length", str(os.stat(filename).st_size))
            conn.putheader('Content-type', mimetype)
            conn.endheaders()

            conn.send(f)

            logger.debug("Request sent; getting response")

            response = conn.getresponse()

            logger.debug("Response received: %r", response.status)

            if response.status not in (200, 201, 204):
                logger.error("Upload failed. Code %r", response.status)
                raise urllib.error.HTTPError(graph_url,
                                        response.status,
                                        "",
                                        response.getheaders(),
                                        response.fp)

            conn.close()

