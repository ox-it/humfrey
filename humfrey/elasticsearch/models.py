import datetime

from django.db import models
from django_longliving.util import get_redis_client, pack

from humfrey.update.models import UpdateDefinition

INDEX_STATUS_CHOICES = (
    ('idle', 'Idle'),
    ('queued', 'Queued'),
    ('active', 'Active'),
)

class Index(models.Model):
    UPDATE_QUEUE = 'humfrey:elasticsearch:index-queue'

    slug = models.SlugField(primary_key=True)
    title = models.CharField(max_length=128)
    query = models.TextField()

    groups = models.CharField(max_length=256, blank=True)
    update_after = models.ManyToManyField(UpdateDefinition, blank=True)

    status = models.CharField(max_length=10, choices=INDEX_STATUS_CHOICES, default='idle')

    last_queued = models.DateTimeField(null=True, blank=True)
    last_started = models.DateTimeField(null=True, blank=True)
    last_completed = models.DateTimeField(null=True, blank=True)

    item_count = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.title

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
