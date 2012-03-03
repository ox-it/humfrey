import collections
from hashlib import sha1
import httplib
import operator
import tempfile
try:
    import json
except ImportError:
    import simplejson as json

from django.conf import settings
from django_longliving.util import pack, unpack, get_redis_client

from humfrey.utils import sparql, resource

class IndexUpdater(object):
    def __init__(self):
        self.endpoint = sparql.Endpoint(settings.ENDPOINT_URL)
        self.client = get_redis_client()

    @classmethod
    def hash_result(cls, value):
        if isinstance(value, list):
            return hash(('l', reduce(operator.xor, (cls.hash_result(i) for i in enumerate(value)))))
        elif isinstance(value, dict):
            return hash(('d', reduce(operator.xor, (cls.hash_result(i) for i in enumerate(value.iteritems())))))
        else:
            return hash(value)

    def update(self, meta):
        hash_key = 'humfrey:elasticsearch:indices:%s' % meta['id']
        results = self.endpoint.query(meta['query'])

        groups = meta.get('group', [])
        fields = results.fields

        results = [dict((k, v._identifier if isinstance(v, resource.BaseResource) else v) for k, v in result._asdict().iteritems()) for result in results]
        new_results = collections.defaultdict(dict)
        for result in results:
            uri = result['uri']
            for key in fields:
                if key in groups:
                    if key not in new_results[uri]:
                        new_results[uri][key] = collections.defaultdict(dict)
                    subresult = {'uri': result[key]}
                    if result[key]:
                        new_results[uri][key][result[key]] = subresult
                elif key.split('_')[0] in groups:
                    if result[key]:
                        subresult[key.split('_', 1)[1]] = result[key]
                else:
                    new_results[uri][key] = result[key]

        for result in new_results.itervalues():
            for key in groups:
                if key in result:
                    result[key] = result[key].values()


        with tempfile.TemporaryFile() as f:
            result_ids = set()
            for result in results:
                result_id = sha1(result['uri']).hexdigest()
                result_ids.add(result_id)
                result_hash = self.hash_result(result)
                print '-'*80
                print result
                print '-'*80

                cached_hash = self.client.hget(hash_key, result_id)
                if cached_hash == result_hash:
                    continue
                self.client.hset(hash_key, result_id, result_hash)

                f.write(json.dumps({'index': {'_id': result_id}}))
                f.write('\n')
                f.write(json.dumps(result))
                f.write('\n')

            result_ids = set(self.client.hkeys(hash_key)) - result_ids
            for result_id in result_ids:
                f.write(json.dumps({'delete': {'_id': result_id}}))
                f.write('\n')

            # If we've nothing to say, don't make a request.
            if not f.tell():
                return

            conn = httplib.HTTPConnection(**settings.ELASTICSEARCH_SERVER)
            conn.connect()
            
            conn.putrequest('POST', '/search/%s/_bulk' % meta['id'])
            conn.putheader("User-Agent", "humfrey")
            conn.putheader("Content-Length", str(f.tell()))
            conn.endheaders()

            f.seek(0)
            for line in f:
                conn.send(line)
        
            response = conn.getresponse()
            print response.status
            print response.read()
            conn.close()
