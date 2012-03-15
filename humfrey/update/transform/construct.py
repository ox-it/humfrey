from __future__ import with_statement

from django.conf import settings

from humfrey.update.transform.base import Transform, TransformException

from humfrey.sparql.endpoint import Endpoint

class NoSuchFile(TransformException):
    pass
class PermissionDeniedToLocalFile(TransformException):
    pass

class Construct(Transform):
    def __init__(self, query, store=None):
        self.query = query
        self.store = None
    def execute(self, transform_manager):
        if self.store:
            store = self.get_store(transform_manager, self.store, query=True)
            endpoint_query = store.query_endpoint
        else:
            endpoint_query = settings.ENDPOINT_QUERY
        
        endpoint = Endpoint(endpoint_query)

        query_filename = self.query.execute(transform_manager)

        with open(transform_manager('nt'), 'w') as output:
            transform_manager.start(self, [query_filename])
            with open(query_filename, 'r') as query:
                result = endpoint.query(query.read())
            
            result.serialize(output, 'nt')
            
            transform_manager.end([output.name])
        return output.name
