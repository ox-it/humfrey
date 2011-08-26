from __future__ import with_statement

import base64
import datetime
import pickle

import rdflib
import redis

from django.conf import settings

from humfrey.update.transform.base import Transform
from humfrey.update.longliving.uploader import Uploader
from humfrey.utils import sparql
from humfrey.utils.namespaces import NS

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
    
    def __init__(self, graph_name, method='PUT'):
        self.graph_name = rdflib.URIRef(graph_name)
        self.method = method

    def execute(self, file_manager, input):
        client = redis.client.Redis(**settings.REDIS_PARAMS)
        
        extension = input.rsplit('.', 1)[-1]
        try:
            serializer = self.formats[extension]
        except KeyError:
            raise ValueError("Unrecognized RDF extension: %r" % extension)
        
        graph = rdflib.ConjunctiveGraph()
        graph.parse(open(input, 'r'),
                    format=serializer,
                    publicID=self.graph_name)
        
        modified = graph.value(self.graph_name, NS['dcterms'].modified,
                               default=rdflib.Literal(datetime.datetime.now()))
        created = graph.value(self.graph_name, NS['dcterms'].created)
        if not created:
            endpoint = sparql.Endpoint(settings.ENDPOINT_QUERY)
            results = endpoint.query(self.created_query % {'graph': self.graph_name.n3()})
            if results:
                created = results[0].date
            else:
                created = modified
        
        graph += (
            (self.graph_name, NS['dcterms'].modified, modified),
            (self.graph_name, NS['dcterms'].created, created),
        )
        
        output = file_manager('nt')
        with open(output, 'w') as f:
            graph.serialize(f, 'nt')

        pubsub = client.pubsub()
        pubsub.subscribe(Uploader.UPLOADED_PUBSUB)
        
        client.rpush(Uploader.QUEUE_NAME,
                     base64.b64encode(pickle.dumps({
            'filename': output,
            'graph_name': self.graph_name,
            'method': self.method,
            'queued_at': datetime.datetime.now(),
        })))
        
        for message in pubsub.listen():
            message = pickle.loads(base64.b64decode(message['data']))
            if message['filename'] == output:
                break
        
        pubsub.unsubscribe(Uploader.UPLOADED_PUBSUB)

