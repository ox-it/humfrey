import collections
from hashlib import sha1
import httplib
import operator
import tempfile
try:
    import json
except ImportError:
    import simplejson as json

import rdflib

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




        with tempfile.TemporaryFile() as f:
            result_ids = set()
            for result in results:
                result_id = sha1(result['uri']).hexdigest()
                result_ids.add(result_id)
                result_hash = self.hash_result(result)
                print '-' * 80
                print result
                print '-' * 80

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

    @classmethod
    def dictify(cls, groups, src):
        dst = {}
        for key in src.iterkeys():
            if not src[key]:
                continue
            x = dst
            for i in key.split('_')[:-1]:
                if i not in x:
                    x[i] = {}
                x = x[i]
            x[key.rsplit('_', 1)[-1]] = src[key]

        for group in groups:
            x = dst
            for key in group[:-1]:
                x = x.get(key, {})
            if group[-1] in x:
                #print "GR", group[-1]
                val = x[group[-1]]
                x[group[-1]] = {cls.get_id(val): val}
                if isinstance(val, dict):
                    val.pop('id', None)

        id = cls.get_id(dst)
        dst.pop('id', None)
        return {id: dst}

    @classmethod
    def get_id(cls, src):
        if 'uri' in src:
            return src['uri']
        elif 'id' in src:
            return src['id']
        else:
            return rdflib.BNode()

    @classmethod
    def merge_dicts(cls, groups, one, two):
        immediate_groups = set(g[0] for g in groups)

        #print "M", one, two

        for id in two:
            if id not in one:
                one[id] = {}
            if isinstance(two[id], basestring):
                one[id] = two[id]
                continue
            for key in two[id]:
                if key in immediate_groups:
                    if key not in one[id]:
                        one[id][key] = {}
                    cls.merge_dicts(set(g[1:] for g in groups if len(g) > 1),
                                    one[id][key], two[id][key])
                elif isinstance(two[id], dict) and isinstance(two[id][key], dict):
                    if key not in one[id]:
                        one[id][key] = {'_singleton': True}
                    one[id][key].update(two[id][key])
                elif two[id][key]:
                    one[id][key] = two[id][key]
        return one

    @classmethod
    def flatten_result(cls, results):
        if results.get('_singleton'):
            del results['_singleton']
            return results
        results = results.values()
        for result in results:
            if not isinstance(result, dict):
                continue
            for k in result:
                if isinstance(result[k], dict):
                    result[k] = cls.flatten_result(result[k])
        return results

    def parse_results(self, meta, results):
        fields = results.fields
        groups = meta.get('group', [])
        groups = tuple(g.split('_') for g in groups)
        groups = tuple(sorted(groups, key=len, reverse=True))

        out = {}

        for result in results:
            result = self.dictify(groups, result)
            self.merge_dicts(groups, out, result)

        return self.flatten_result(out)
