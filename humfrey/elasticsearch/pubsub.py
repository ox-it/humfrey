from django_longliving.decorators import pubsub_watcher

from humfrey.update.longliving.updater import Updater
from humfrey.elasticsearch.models import Index


@pubsub_watcher(channel=Updater.UPDATED_CHANNEL, priority=80)
def update_search_indexes(channel, data):
    for index in Index.objects.filter(update_after__slug=data['slug']):
        index.queue()

