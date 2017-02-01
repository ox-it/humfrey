import datetime

from celery.task import task

from humfrey.signals import update_completed

from .models import Index
from .update import IndexUpdater

@task(name='humfrey.elasticsearch.update_indexes_after_dataset_update', ignore_result=True)
def update_indexes_after_dataset_update(sender, update_definition, store_graphs, when, **kwargs):
    for index in Index.objects.filter(update_after=update_definition):
        update_index(index)

update_completed.connect(update_indexes_after_dataset_update.delay)

@task(name='humfrey.elasticsearch.update_index', ignore_result=True)
def update_index(index):
    if isinstance(index, str):
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