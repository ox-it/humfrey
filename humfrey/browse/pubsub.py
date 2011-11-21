from django.conf import settings
from django_longliving.decorators import pubsub_watcher

from humfrey.update.longliving.updater import Updater
from humfrey.browse import update

@pubsub_watcher(channel=Updater.UPDATED_CHANNEL, priority=100)
def update_list(client, channel, data):
    browse_lists = getattr(settings, 'BROWSE_LISTS') or ()

    for browse_list in browse_lists:
        if data['slug'] in browse_list.get('update_triggered_by', ()):
            update.update_list(client, browse_list)
