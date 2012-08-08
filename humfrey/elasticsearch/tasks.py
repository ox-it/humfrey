import datetime

from celery.task import task

from .models import Index
from .update import IndexUpdater

@task(name='humfrey.elasticsearch.update_indexes_after_dataset_update')
def update_indexes_after_dataset_update(update_log, graphs, updated):
    for index in Index.objects.filter(update_after=update_log.update_definition):
        update_index(index)

@task(name='humfrey.elasticsearch.update_index')
def update_index(index):
    if isinstance(index, basestring):
        index = Index.objects.get(slug=index)
    index.status = 'active'
    index.last_started = datetime.datetime.now()
    index.save()
    try:
        index_updater = IndexUpdater()
        index_updater.update(index)
    finally:
        index.status = 'idle'
        index.last_completed = datetime.datetime.now()
        index.update_mapping = False
        index.save()