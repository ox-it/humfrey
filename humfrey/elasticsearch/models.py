import datetime
import json

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
            self.update_mapping = True
        if self.update_mapping:
            self.mapping = json.dumps(self.migrate_mapping(json.loads(self.mapping)), indent=2)
        return super(Index, self).save(*args, **kwargs)

    def migrate_mapping_properties(self, properties):
        for property in properties:

            if 'properties' in property:
                self.migrate_mapping_properties(property['properties'].values())
            if property.get('type') == 'string':
                if property.get('index') == 'not_analyzed':
                    property['type'] = 'keyword'
                    del property['index']
                else:
                    property['type'] = 'text'
            if '_boost' in property:
                del property['_boost']
            if 'boost' in property:
                del property['boost']

    def migrate_mapping(self, mapping):
        for type_mapping in mapping.values():
            properties = type_mapping.get('properties', {})
            self.migrate_mapping_properties(properties.values())
            type_mapping.pop('_boost', None)
            properties['uri'] = {'type': 'keyword'}
            properties['location'] = {'type': 'geo_point'}
        if '_boost' in mapping:
            del mapping['_boost']

        return mapping

    def _get_url(self, store, path, pattern):
        params = {'slug': self.slug,
                  'store': store.slug}
        params.update(settings.ELASTICSEARCH_SERVER)
        if not path:
            pattern = 'http://%(host)s:%(port)d' + pattern
        return pattern % params

    def get_index_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s')

    def get_index_delete_by_query_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/_delete_by_query')

    def get_index_stats_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/_stats')

    def get_type_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/')

    def get_type_status_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/_status')

    def get_bulk_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/_bulk')

    def get_mapping_url(self, store, path=False):
        return self._get_url(store, path, '/%(store)s/_mapping')

    class Meta:
        verbose_name_plural = 'indexes'

    def __str__(self):
        return self.title

    def __repr__(self):
        return "<Index '{}'>".format(self.pk)

    def queue(self):
        if self.status != 'idle':
            return

        self.status = 'queued'
        self.last_queued = datetime.datetime.now()
        self.save()

        from . import tasks
        tasks.update_index.delay(index_id=self.pk)
