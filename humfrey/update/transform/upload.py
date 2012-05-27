from __future__ import with_statement

import base64
import datetime
import logging
import pickle

import pytz
import rdflib
import redis

from django.conf import settings

from humfrey.update.transform.base import Transform
from humfrey.update.uploader import Uploader
from humfrey.sparql.endpoint import Endpoint
from humfrey.utils.namespaces import NS

logger = logging.getLogger(__name__)

class Upload(Transform):
    formats = {
        'rdf': 'xml',
        'n3': 'n3',
        'ttl': 'n3',
        'nt': 'nt',
    }

    created_query = """
        SELECT ?date WHERE {
          GRAPH %(graph)s {
            %(graph)s dcterms:created ?date
          }
        }
    """

    site_timezone = pytz.timezone(settings.TIME_ZONE)

    def __init__(self, graph_name, method='PUT', store=None, stores=None):
        self.graph_name = rdflib.URIRef(graph_name)
        self.method = method
        self.stores = stores or []
        if not stores:
            self.stores.append(store)

    def execute(self, transform_manager, input):
        for store in self.stores:
            if store:
                store = self.get_store(transform_manager, store, update=True)
                endpoint_query = store.query_endpoint
            else:
                endpoint_query = settings.ENDPOINT_QUERY

        transform_manager.start(self, [input])

        logger.debug("Starting upload of %r", input)

        client = self.get_redis_client()

        extension = input.rsplit('.', 1)[-1]
        try:
            serializer = self.formats[extension]
        except KeyError:
            logger.exception("Unrecognized RDF extension: %r", extension)
            raise

        graph = rdflib.ConjunctiveGraph()
        graph.parse(open(input, 'r'),
                    format=serializer,
                    publicID=self.graph_name)

        logger.debug("Parsed graph")

        datetime_now = self.site_timezone.localize(datetime.datetime.now().replace(microsecond=0))
        modified = graph.value(self.graph_name, NS['dcterms'].modified,
                               default=rdflib.Literal(datetime_now))
        created = graph.value(self.graph_name, NS['dcterms'].created)
        if not created:
            logger.debug("Getting created date from %r", endpoint_query)
            endpoint = Endpoint(endpoint_query)
            results = list(endpoint.query(self.created_query % {'graph': self.graph_name.n3()}))
            if results:
                created = results[0].date
            else:
                created = modified

        graph += (
            (self.graph_name, NS['dcterms'].modified, modified),
            (self.graph_name, NS['dcterms'].created, created),
        )

        logger.debug("About to serialize and queue")

        output = transform_manager('rdf')
        with open(output, 'w') as f:
            graph.serialize(f)

        uploader = Uploader()
        uploader.upload(stores=self.stores,
                        graph_name=self.graph_name,
                        filename=output,
                        method=self.method,
                        mimetype='application/rdf+xml')

        transform_manager.end([self.graph_name])
        for store in self.stores:
            transform_manager.touched_graph(store, self.graph_name)
