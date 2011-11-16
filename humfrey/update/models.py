import datetime
import logging

from django.db import models
from django.contrib.auth.models import User
from django_longliving.util import pack, get_redis_client

from humfrey.update.utils import evaluate_pipeline

DEFINITION_STATUS_CHOICES = (
    ('idle', 'Idle'),
    ('queued', 'Queued'),
    ('active', 'Active'),
)

class UpdateDefinition(models.Model):
    UPDATE_QUEUE = 'humfrey:update:update-queue'

    class AlreadyQueued(AssertionError):
        pass

    slug = models.SlugField(primary_key=True)
    title = models.CharField(max_length=80)
    description = models.TextField(blank=True)

    cron_schedule = models.TextField(blank=True)

    change_users = models.ManyToManyField(User, related_name="update_definitions_change", blank=True)
    execute_users = models.ManyToManyField(User, related_name="update_definitions_execute", blank=True)

    status = models.CharField(max_length=10, choices=DEFINITION_STATUS_CHOICES)

    last_queued = models.DateTimeField(null=True, blank=True)
    last_started = models.DateTimeField(null=True, blank=True)
    last_completed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('title',)
        permissions = (
            ("execute_updatedefinition", "Can perform an update"),
        )

    def can_edit(self, user):
        if user.has_perm("change_updatedefinition"):
            return True
        return bool(self.change_users.filter(change_users=user).count)

    def can_execute(self, user):
        if user.has_perm("execute_updatedefinition"):
            return True
        return bool(self.execute_users.filter(change_users=user).count)

    def queue(self, trigger, user=None):
        if self.status != 'idle':
            raise self.AlreadyQueued()
        self.status = 'queued'
        self.last_queued = datetime.datetime.now()
        self.save()

        redis_client = get_redis_client()
        redis_client.lpush(self.UPDATE_QUEUE, pack(self.slug))

class UpdatePipeline(models.Model):
    update_definition = models.ForeignKey(UpdateDefinition, related_name="pipelines")
    value = models.TextField()

    def save(self, *args, **kwargs):
        try:
            evaluate_pipeline(self.value)
        except (SyntaxError, NameError), e:
            raise ValueError(e)
        return super(UpdatePipeline, self).save(*args, **kwargs)