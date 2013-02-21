from __future__ import with_statement

import datetime
import logging

import pytz
import rdflib

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

    def __init__(self, graph_name, method='PUT'):
        self.graph_name = rdflib.URIRef(graph_name)
        self.method = method

    def execute(self, transform_manager, input):
        transform_manager.start(self, [input])

        logger.debug("Starting upload of %r", input)

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
            logger.debug("Getting created date from %r", transform_manager.store.query_endpoint)
            endpoint = Endpoint(transform_manager.store.query_endpoint)
            results = list(endpoint.query(self.created_query % {'graph': self.graph_name.n3()}))
            if results:
                created = results[0].date
            else:
                created = modified

        graph += (
            (self.graph_name, NS.rdf.type, NS.sd.Graph),
            (self.graph_name, NS.dcterms.modified, modified),
            (self.graph_name, NS.dcterms.created, created),
        )

        logger.debug("About to serialize")

        output = transform_manager('rdf')
        with open(output, 'w') as f:
            graph.serialize(f)

        logger.debug("Serialization done; about to upload")

        uploader = Uploader()
        uploader.upload(stores=(transform_manager.store,),
                        graph_name=self.graph_name,
                        filename=output,
                        method=self.method,
                        mimetype='application/rdf+xml')

        logger.debug("Upload complete")

        transform_manager.end([self.graph_name])
        transform_manager.touched_graph(self.graph_name)
