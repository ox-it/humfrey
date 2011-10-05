from __future__ import with_statement

import base64
import collections
import datetime
import os
import pickle

from lxml import etree
import redis

from django.core.management.base import BaseCommand
from django.conf import settings

from humfrey.browse.views import IndexView, ListView
from humfrey.utils import sparql, resource


class Command(BaseCommand):
    def pack(self, value):
        return base64.b64encode(pickle.dumps(value))
    def unpack(self, value):
        return pickle.loads(base64.b64decode(value))
    def get_redis_client(self):
        return redis.client.Redis(**settings.REDIS_PARAMS)

    def handle(self, *args, **options):
        client = self.get_redis_client()

        lists = []
        for browse_list in settings.BROWSE_LISTS:
            meta = self.update_list(client, browse_list)
            client.hset(ListView.LIST_META, meta['id'], self.pack(meta))
            lists.append(meta)
        lists.sort(key=lambda l: l['name'])

        client.set(IndexView.LIST_META, self.pack(lists))

    def update_list(self, client, browse_list):
        endpoint = sparql.Endpoint(settings.ENDPOINT_URL)
        results = endpoint.query(browse_list['query'])
        print dir(results)

        meta = browse_list.copy()
        meta['fields'] = results.fields
        meta['count'] = len(results)

        sorted_fields = sorted(meta['fields'])

        groups = meta.get('group', [])

        results = [dict((k, v._identifier if isinstance(v, resource.BaseResource) else v) for k, v in result._asdict().iteritems()) for result in results]
        new_results = collections.defaultdict(dict)
        for result in results:
            uri = result['uri']
            for key in sorted_fields:
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

        results = sorted(new_results.itervalues(), key=lambda r: r['uri'])

        for field in [f for f in meta['fields'] if not f.split('_')[0] in groups]:
            results.sort(key=lambda result: result[field])
            key = ListView.LIST_ITEMS % (meta['id'], field)
            print key
            client.delete(key)
            for result in results:
                client.rpush(key, self.pack(result))

        return meta


if __name__ == '__main__':
    import sys
    Command().handle(*sys.argv[1:])
