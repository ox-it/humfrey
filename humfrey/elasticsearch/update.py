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
        self.endpoint = sparql.Endpoint(settings.ENDPOINT_QUERY)
        self.client = get_redis_client()

    @classmethod
    def hash_result(cls, value):
        def recursive_sort(value):
            if isinstance(value, dict):
                for subvalue in value.itervalues():
                    recursive_sort(subvalue)
            elif isinstance(value, list):
                for subvalue in value:
                    recursive_sort(subvalue)
                value.sort()
        return hash(json.dumps(recursive_sort(value)))

    def update(self, index):
        hash_key = 'humfrey:elasticsearch:indices:%s' % index.slug
        results = self.endpoint.query(index.query)

        results = self.parse_results(index, results)

        with tempfile.TemporaryFile() as f:
            result_ids = set()
            for result in results:
                result_id = sha1(result['uri']).hexdigest()
                result_ids.add(result_id)
                result_hash = self.hash_result(result)

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

            conn.putrequest('POST', '/search/%s/_bulk' % index.slug)
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

        return len(results)

    @classmethod
    def dictify(cls, groups, src):
        dst = {}
        for key, value in src.iteritems():
            print "K", key, value
            if not value:
                continue
            if isinstance(value, rdflib.Literal):
                print "LIT", repr(value), repr(value.toPython())
                try:
                    value = value.toPython()
                except ValueError:
                    raise
            x = dst
            for i in key.split('_')[:-1]:
                if i not in x:
                    x[i] = {}
                x = x[i]
            x[key.rsplit('_', 1)[-1]] = value

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
        if not isinstance(src, dict):
            return rdflib.BNode()
        if 'uri' in src:
            return src['uri']
        elif 'id' in src:
            return src['id']
        else:
            return rdflib.BNode()

    @classmethod
    def merge_dicts(cls, groups, one, two):
        immediate_groups = set(g[0] for g in groups)

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
            for key, value in results.items():
                if not value or key in ('_singleton', 'id'):
                    del results[key]
            return results
        results = results.values()
        for result in results:
            if not isinstance(result, dict):
                continue
            for k in list(result):
                if isinstance(result[k], dict):
                    result[k] = cls.flatten_result(result[k])
                elif k == 'id':
                    del result[k]
        results[:] = filter(bool, results)
        return results

    def parse_results(self, index, results):
        fields = results.fields
        groups = index.groups.split()
        groups = tuple(g.split('_') for g in groups)
        groups = tuple(sorted(groups, key=len, reverse=True))

        out = {}

        for result in results:
            result = sparql.Result(fields, [r._identifier if isinstance(r, resource.BaseResource) else r for r in result])
            result = self.dictify(groups, result)
            self.merge_dicts(groups, out, result)

        return self.flatten_result(out)
