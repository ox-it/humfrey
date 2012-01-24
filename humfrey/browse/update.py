import collections

from django.conf import settings
from django_longliving.util import pack, unpack
import redis

from humfrey.browse.views import IndexView, ListView
from humfrey.utils import sparql, resource

def update_list(client, browse_list):
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
            client.rpush(key, pack(result))


    client.hset(ListView.LIST_META, meta['id'], pack(meta))

    # Update the list of all lists, avoiding races by wrapping everything
    # in a transaction pipeline.
    pipeline = client.pipeline()
    while True:
        pipeline.watch(IndexView.LIST_META)
        list_meta = unpack(pipeline.get(IndexView.LIST_META))
        list_meta = filter(lambda l:l['id'] != browse_list['id'])
        list_meta.append(meta)
        list_meta.sort(key=lambda l:l['name'])
        pipeline.set(IndexView.LIST_META, pack(list_meta))
        try:
            pipeline.execute()
        except redis.WatchError:
            continue
        break
