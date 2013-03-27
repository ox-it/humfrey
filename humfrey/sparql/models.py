from django.db import models
from django.conf import settings
from django.contrib.auth.models import User, Group

from .endpoint import Endpoint

DEFAULT_STORE_SLUG = getattr(settings, 'DEFAULT_STORE_SLUG', 'public')

class Store(models.Model):
    slug = models.SlugField(primary_key=True)
    name = models.CharField(max_length=128)

    query_endpoint = models.URLField()
    update_endpoint = models.URLField(null=True, blank=True)
    graph_store_endpoint = models.URLField(null=True, blank=True)

    def __unicode__(self):
        return self.name

    def query(self, *args, **kwargs):
        return Endpoint(self.query_endpoint).query(*args, **kwargs)

    class Meta:
        permissions = (('administer_store', 'can administer'),
                       ('query_store', 'can query'),
                       ('update_store', 'can update'))

class UserPrivileges(models.Model):
    user = models.ForeignKey(User, null=True, blank=True)
    group = models.ForeignKey(Group, null=True, blank=True)

    allow_concurrent_queries = models.BooleanField()
    disable_throttle = models.BooleanField()
    throttle_threshold = models.FloatField(null=True, blank=True)
    deny_threshold = models.FloatField(null=True, blank=True)
    intensity_decay = models.FloatField(null=True, blank=True)

    disable_timeout = models.BooleanField()
    maximum_timeout = models.IntegerField(null=True)
