import base64
import datetime
import logging
import pickle

from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.template.base import mark_safe
from django_longliving.util import pack, get_redis_client
from object_permissions import register

from humfrey.update.utils import evaluate_pipeline

DEFINITION_STATUS_CHOICES = (
    ('idle', 'Idle'),
    ('queued', 'Queued'),
    ('active', 'Active'),
)

def permission_check(model, perm):
    name = 'update.%s_%s' % (perm, model)
    def f(self, user):
        return user.has_perm(name) or user.has_perm(name, self)
    return f

class UpdateDefinition(models.Model):
    UPDATE_QUEUE = 'humfrey:update:update-queue'

    class AlreadyQueued(AssertionError):
        pass

    slug = models.SlugField(primary_key=True)
    title = models.CharField(max_length=80)
    description = models.TextField(blank=True)

    owner = models.ForeignKey(User, related_name='owned_updates')

    cron_schedule = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=DEFINITION_STATUS_CHOICES, default='idle')
    last_log = models.ForeignKey('UpdateLog', null=True, blank=True)

    last_queued = models.DateTimeField(null=True, blank=True)
    last_started = models.DateTimeField(null=True, blank=True)
    last_completed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('title',)
        permissions = (
            ("admin", "May use the dataset update admin pages"),
            ("view_updatedefinition", "Can view the update definition"),
            ("execute_updatedefinition", "Can perform an update"),
            ("administer_updatedefinition", "Can administer an update definition"),
        )

    can_view = permission_check('updatedefinition', 'view')
    can_change = permission_check('updatedefinition', 'change')
    can_execute = permission_check('updatedefinition', 'execute')
    can_delete = permission_check('updatedefinition', 'delete')
    can_administer = permission_check('updatedefinition', 'administer')
    receives_notifications = permission_check('updatedefinition', 'notifications')

    def queue(self, trigger, user=None, silent=False):
        if self.status != 'idle':
            if silent:
                return
            raise self.AlreadyQueued()
        self.status = 'queued'
        self.last_queued = datetime.datetime.now()

        update_log = UpdateLog.objects.create(update_definition=self,
                                              user=user,
                                              trigger=trigger,
                                              queued=self.last_queued)

        self.last_log = update_log
        self.save()

        redis_client = get_redis_client()
        redis_client.lpush(self.UPDATE_QUEUE, pack(update_log))

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('update:definition-detail', args=[self.slug])

register(['update.administer_updatedefinition',
          'update.view_updatedefinition',
          'update.change_updatedefinition',
          'update.execute_updatedefinition',
          'update.delete_updatedefinition',
          'update.notifications_updatedefinition'],
         UpdateDefinition, 'update')

class WithLevels(object):
    levels = {'errors': {'label': 'errors',
                         'icon': 'gnome-icons/32x32/dialog-error.png'},
              'warnings': {'label': 'warnings',
                           'icon': 'gnome-icons/32x32/dialog-warning.png'},
              'success': {'label': 'success',
                          'icon': 'gnome-icons/32x32/emblem-default.png'},
              'inprogress': {'label': 'in progress',
                             'icon': 'gnome-icons/32x32/system-run.png'}}

    @property
    def level(self):
        level = self.log_level
        if level >= logging.ERROR:
            return 'errors'
        elif level >= logging.WARNING:
            return 'warnings'
        elif level >= 0:
            return 'success'
        else:
            return 'inprogress'

    def get_level_display(self):
        return self.levels[self.level]['label']

    def get_level_icon(self):
        return self.levels[self.level]['icon']

class UpdateLog(models.Model, WithLevels):
    update_definition = models.ForeignKey(UpdateDefinition, related_name="update_log")
    user = models.ForeignKey(User, related_name='update_log', blank=True, null=True)
    forced = models.BooleanField()

    trigger = models.CharField(max_length=80)
    log_level = models.SmallIntegerField(null=True, blank=True)

    queued = models.DateTimeField(null=True, blank=True)
    started = models.DateTimeField(null=True, blank=True)
    completed = models.DateTimeField(null=True, blank=True)

    def get_absolute_url(self):
        return reverse('update:log-detail', args=[self.update_definition.slug, self.id])

    @property
    def records(self):
        return self.updatelogrecord_set.all().order_by('when')


    def __unicode__(self):
        return '%s at %s' % (self.update_definition, self.queued)

class UpdateLogRecord(models.Model, WithLevels):
    update_log = models.ForeignKey(UpdateLog)
    when = models.DateTimeField()
    _record = models.TextField()
    log_level = models.SmallIntegerField()

    def _set_record(self, value):
        self._record = base64.b64encode(pickle.dumps(value))
        self.log_level = value['levelno']
        self.when = value['time']
    def _get_record(self):
        if not hasattr(self, '_record_cache'):
            self._record_cache = pickle.loads(base64.b64decode(self._record))
        return self._record_cache
    record = property(_get_record, _set_record)

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

class LocalFile(models.Model):
    name = models.CharField(max_length=255, unique=True, db_index=True)
    content = models.FileField(upload_to=settings.UPDATE_FILES_DIRECTORY)
    publish = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return reverse('update:file-detail', args=[self.name])
    def get_contents(self):
        self.content.open()
        try:
            return self.content.read()
        except AttributeError:
            return None
        finally:
            self.content.close()
    def is_text(self):
        self.content.open()
        try:
            data = self.content.read(512)
        except:
            return False
        finally:
            self.content.close()
        try:
            data.decode('utf-8')
        except UnicodeDecodeError, e:
            # Couldn't decode as UTF-8/ASCII, and not because we'd
            # broken off the end of a multi-byte character. 
            if e.start < 507:
                return False
        # Check for any low-ordinal bytes
        return not any([ord(b) < 0x0a for b in data])

    can_view = permission_check('localfile', 'view')
    can_change = permission_check('localfile', 'change')
    can_delete = permission_check('localfile', 'delete')
    can_administer = permission_check('localfile', 'administer')

register(['update.view_localfile',
          'update.change_localfile',
          'update.delete_localfile',
          'update.administer_localfile'],
         LocalFile, 'update')
