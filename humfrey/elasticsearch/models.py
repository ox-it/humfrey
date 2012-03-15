import datetime
try:
    import json
except ImportError:
    import simplejson

from django.conf import settings
from django.db import models
from django_longliving.util import get_redis_client, pack

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

    store = models.ForeignKey(Store, null=True)

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

    @property
    def index_url(self):
        params = settings.ELASTICSEARCH_SERVER.copy()
        params['slug'] = self.slug
        return 'http://%(host)s:%(port)d/%(slug)s' % params

    @property
    def mapping_url(self):
        print self.index_url
        return self.index_url + '/_mapping'

    @property
    def status_url(self):
        return self.index_url + '/_status'

    class Meta:
        verbose_name_plural = 'indexes'

    def queue(self):
        if self.status != 'idle':
            return

        self.status = 'queued'
        self.last_queued = datetime.datetime.now()
        self.save()

        redis_client = get_redis_client()
        redis_client.lpush(self.UPDATE_QUEUE, pack(self))
