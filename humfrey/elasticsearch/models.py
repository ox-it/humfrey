import datetime
import json

from celery.execute import send_task
from django.conf import settings
from django.db import models

from humfrey.sparql.models import Store
from humfrey.update.models import UpdateDefinition

INDEX_STATUS_CHOICES = (
    ('idle', 'Idle'),
    ('queued', 'Queued'),
    ('active', 'Active'),
)

class Index(models.Model):
    UPDATE_QUEUE = 'humfrey:elasticsearch:index-queue'

    slug = models.CharField(max_length=50, primary_key=True)

    stores = models.ManyToManyField(Store, blank=True)

    title = models.CharField(max_length=128)
    query = models.TextField()

    mapping = models.TextField(blank=True)
    update_mapping = models.BooleanField()

    groups = models.CharField(max_length=256, blank=True)
    update_after = models.ManyToManyField(UpdateDefinition, blank=True)

    status = models.CharField(max_length=10, choices=INDEX_STATUS_CHOICES, default='idle')

    last_queued = models.DateTimeField(null=True, blank=True)
    last_started = models.DateTimeField(null=True, blank=True)
    last_completed = models.DateTimeField(null=True, blank=True)

    item_count = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.title

    def __init__(self, *args, **kwargs):
        super(Index, self).__init__(*args, **kwargs)
        self._original_mapping = self.mapping

    def save(self, *args, **kwargs):
        if self._original_mapping != self.mapping:
            self.mapping = json.dumps(json.loads(self.mapping), indent=2)
            self.update_mapping = True
        return super(Index, self).save(*args, **kwargs) 

    def _get_url(self, store, path, pattern):
        params = {'slug': self.slug,
                  'store': store.slug}
        params.update(settings.ELASTICSEARCH_SERVER)
        if not path:
            pattern = 'http://%(host)s:%(port)d' + pattern
        return pattern % params

    def get_index_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s')

    def get_index_status_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/_status')

    def get_type_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/%(slug)s')

    def get_type_status_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/%(slug)s/_status')

    def get_bulk_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/%(slug)s/_bulk')

    def get_mapping_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/%(slug)s/_mapping')

    class Meta:
        verbose_name_plural = 'indexes'

    def queue(self):
        if self.status != 'idle':
            return

        self.status = 'queued'
        self.last_queued = datetime.datetime.now()
        self.save()

        send_task('humfrey.elasticsearch.update_index', kwargs={'index': self.slug})
