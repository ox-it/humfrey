from hashlib import sha1
import httplib
import tempfile
import urllib2
try:
    import json
except ImportError:
    import simplejson as json

import rdflib

from django.conf import settings
from django_longliving.util import get_redis_client

from humfrey.utils import resource
from humfrey.sparql.endpoint import Endpoint, Result

class IndexUpdater(object):
    def __init__(self):
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
        for store in index.stores.all():
            self.update_for_store(index, store)

    def update_for_store(self, index, store):
        hash_key = 'humfrey:elasticsearch:indices:%s:%s' % (index.slug, store.slug)
        endpoint = Endpoint(store.query_endpoint)
        results = endpoint.query(index.query)

        try:
            urllib2.urlopen(index.get_index_status_url(store))
            index_exists = True
        except urllib2.HTTPError, e:
            if e.code == httplib.NOT_FOUND:
                index_exists = False
                index.update_mapping = True

                request = urllib2.Request(index.get_index_url(store))
                request.get_method = lambda: 'PUT'
                urllib2.urlopen(request)
            else:
                raise

        if index.update_mapping:
            index.update_mapping = False
            if index_exists:
                request = urllib2.Request(index.get_type_url(store))
                request.get_method = lambda : 'DELETE'
                urllib2.urlopen(request)

            if index.mapping:
                request = urllib2.Request(index.get_mapping_url(store), index.mapping)
                request.get_method = lambda : 'PUT'
                urllib2.urlopen(request)

        results = self.parse_results(index, results)

        with tempfile.TemporaryFile() as f:
            result_ids = set()
            result_count = 0
            for result in results:
                result_count += 1

                result_id = sha1(result['uri']).hexdigest()[:8]
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

            conn.putrequest('POST', index.get_bulk_url(store, path=True))
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

        return result_count

    @classmethod
    def dictify(cls, groups, src):
        dst = {}
        for key, value in src.iteritems():
            if value is None:
                continue
            if isinstance(value, rdflib.Literal):
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

    @classmethod
    def parse_results(cls, index, results):
        groups = index.groups.split()
        groups = tuple(g.split('_') for g in groups)
        groups = tuple(sorted(groups, key=len, reverse=True))

        out = None
        current_uri = None

        for result in results:
            if result['uri'] != current_uri:
                if out:
                    yield cls.flatten_result(out)[0]
                out = {}
                current_uri = result['uri']
            result = cls.dictify(groups, result)
            cls.merge_dicts(groups, out, result)

        if out:
            yield cls.flatten_result(out)[0]