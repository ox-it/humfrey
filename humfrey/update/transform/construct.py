from __future__ import with_statement

from django.conf import settings

from humfrey.update.transform.base import Transform, TransformException

from humfrey.sparql.endpoint import Endpoint

class NoSuchFile(TransformException):
    pass
class PermissionDeniedToLocalFile(TransformException):
    pass

class Construct(Transform):
    def __init__(self, query):
        self.query = query
    def execute(self, transform_manager):

        endpoint = Endpoint(transform_manager.store.query_endpoint)

        if isinstance(self.query, basestring):
            query = self.query
        else:
            query_filename = self.query.execute(transform_manager)
            with open(query_filename, 'r') as query_file:
                query = query_file.read()

        with open(transform_manager('nt'), 'w') as output:
            transform_manager.start(self, [])
            result = endpoint.query(query)

            result.serialize(output, 'nt')

            transform_manager.end([output.name])
        return output.name
