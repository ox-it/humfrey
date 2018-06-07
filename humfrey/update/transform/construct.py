from django.conf import settings

from humfrey.update.transform.base import Transform, TransformException

from humfrey.sparql.endpoint import Endpoint
from humfrey.streaming import serialize


class Construct(Transform):
    def __init__(self, query):
        self.query = query
    def execute(self, transform_manager):

        endpoint = Endpoint(transform_manager.store.query_endpoint, preferred_media_types=('text/plain',))

        if isinstance(self.query, str):
            query = self.query
        else:
            query_filename = self.query.execute(transform_manager)
            with open(query_filename, 'r') as query_file:
                query = query_file.read()

        with open(transform_manager('nt'), 'wb') as output:
            transform_manager.start(self, [])
            serialize(endpoint.query(query, defer=True), output)
            transform_manager.end([output.name])
        return output.name
