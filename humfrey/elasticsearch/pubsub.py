from django.conf import settings

from django_longliving.decorators import pubsub_watcher

from humfrey.update.longliving.updater import Updater
from humfrey.elasticsearch.update import IndexUpdater


@pubsub_watcher(channel=Updater.UPDATED_CHANNEL, priority=80)
def update_search_indexes(channel, data):
    index_updater = IndexUpdater()
    for meta in settings.ELASTICSEARCH_INDEXES:
        if data['slug'] in meta['reindex_on_change']:
            index_updater.update(meta)
