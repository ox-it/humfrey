import datetime

from celery import shared_task
from django.dispatch import receiver

from humfrey.signals import update_completed
from humfrey.sparql.models import Store

from .models import Index
from .update import IndexUpdater

@shared_task(name='humfrey.elasticsearch.update_indexes_after_dataset_update', ignore_result=True)
def update_indexes_after_dataset_update(update_definition_id):
    for index in Index.objects.filter(update_after__pk=update_definition_id):
        update_index.delay(index.pk)


@receiver(update_completed)
def update_completed_receiver(sender, update_definition_id, **kwargs):
    update_indexes_after_dataset_update.delay(update_definition_id=update_definition_id)


@shared_task(name='humfrey.elasticsearch.update_index', ignore_result=True)
def update_index(index_id=None, store_id=None):
    print("A", repr(index_id), repr(store_id))
    indexes = Index.objects.all()
    stores = Store.objects.all()
    if index_id:
        indexes = indexes.filter(pk=index_id)
    if store_id:
        stores = stores.filter(pk=store_id)

    for index in indexes:
        index.status = 'active'
        index.last_started = datetime.datetime.now()
        index.save()
        try:
            index_updater = IndexUpdater()
            print("B", repr(index), repr(stores))
            index_updater.update(index, stores=stores)
        finally:
            index.status = 'idle'
            index.last_completed = datetime.datetime.now()
            index.update_mapping = False
            index.save()
