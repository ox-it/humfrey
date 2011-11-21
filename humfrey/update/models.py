import datetime
import logging

from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
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

    view_users = models.ManyToManyField(User, related_name="update_definitions_view", blank=True)
    change_users = models.ManyToManyField(User, related_name="update_definitions_change", blank=True)
    execute_users = models.ManyToManyField(User, related_name="update_definitions_execute", blank=True)
    delete_users = models.ManyToManyField(User, related_name="update_definitions_delete", blank=True)

    status = models.CharField(max_length=10, choices=DEFINITION_STATUS_CHOICES, default='idle')

    last_queued = models.DateTimeField(null=True, blank=True)
    last_started = models.DateTimeField(null=True, blank=True)
    last_completed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('title',)
        permissions = (
            ("admin", "May use the dataset update admin pages"),
            ("view_updatedefinition", "Can view the update definition"),
            ("execute_updatedefinition", "Can perform an update"),
        )

    def can_view(self, user):
        if user.has_perm("update.view_updatedefinition"):
            return True
        return bool(UpdateDefinition.objects.filter(pk=self.pk, view_users=user).count())

    def can_change(self, user):
        if user.has_perm("update.change_updatedefinition" if self.pk else "update.add_updatedefinition"):
            return True
        return bool(UpdateDefinition.objects.filter(pk=self.pk, change_users=user).count())

    def can_execute(self, user):
        if user.has_perm("update.execute_updatedefinition"):
            return True
        return bool(UpdateDefinition.objects.filter(pk=self.pk, execute_users=user).count())

    def can_delete(self, user):
        if user.has_perm("update.delete_updatedefinition"):
            return True
        return bool(UpdateDefinition.objects.filter(pk=self.pk, delete_users=user).count())

    def queue(self, trigger, user=None, silent=False):
        if self.status != 'idle':
            if silent:
                return
            raise self.AlreadyQueued()
        self.status = 'queued'
        self.last_queued = datetime.datetime.now()
        self.save()

        update_log = UpdateLog.objects.create(update_definition=self,
                                              user=user,
                                              trigger=trigger,
                                              queued=self.last_queued)

        redis_client = get_redis_client()
        redis_client.lpush(self.UPDATE_QUEUE, pack(update_log))

    def get_absolute_url(self):
        return reverse('update:definition-detail', args=[self.slug])

class UpdateLog(models.Model):
    update_definition = models.ForeignKey(UpdateDefinition, related_name="update_log")
    user = models.ForeignKey(User, related_name='update_log', blank=True, null=True)

    trigger = models.CharField(max_length=80)

    queued = models.DateTimeField(null=True, blank=True)
    started = models.DateTimeField(null=True, blank=True)
    completed = models.DateTimeField(null=True, blank=True)

class UpdatePipeline(models.Model):
    update_definition = models.ForeignKey(UpdateDefinition, related_name="pipelines")
    value = models.TextField()

    def save(self, *args, **kwargs):
        try:
            evaluate_pipeline(self.value)
        except (SyntaxError, NameError), e:
            raise ValueError(e)
        return super(UpdatePipeline, self).save(*args, **kwargs)

class UpdateVariable(models.Model):
    update_definition = models.ForeignKey(UpdateDefinition, related_name="variables")
    name = models.TextField()
    value = models.TextField()
