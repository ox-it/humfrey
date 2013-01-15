from django.db import models
from django.contrib.auth.models import User, Group

from .endpoint import Endpoint

from object_permissions import register

def permission_check(model, perm):
    name = 'sparql.%s_%s' % (perm, model)
    def f(self, user):
        return user.has_perm(name) or user.has_perm(name, self)
    return f

class Store(models.Model):
    slug = models.SlugField(primary_key=True)
    name = models.CharField(max_length=128)

    query_endpoint = models.URLField()
    update_endpoint = models.URLField(null=True, blank=True)
    graph_store_endpoint = models.URLField(null=True, blank=True)

    can_administer = permission_check('store', 'administer')
    can_query = permission_check('store', 'query')
    can_update = permission_check('store', 'update')

    def __unicode__(self):
        return self.name

    def query(self, *args, **kwargs):
        return Endpoint(self.query_endpoint).query(*args, **kwargs)

    class Meta:
        permissions = (('administer_store', 'can administer'),
                       ('query_store', 'can query'),
                       ('update_store', 'can update'))

register(['sparql.administer_store',
          'sparql.query_store',
          'sparql.update_store'],
         Store, 'sparql')

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
