import hashlib

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models

from celery.execute import send_task
import rdflib

from humfrey.sparql.models import Store

STATE_CHOICES = (
    ('new', 'New'),
    ('queued', 'Queued'),
    ('invalid', 'Invalid pingback'),
    ('processing', 'Being processed'),
    ('pending', 'Pending moderation'),
    ('accepted', 'Accepted'),
    ('rejected', 'Rejected'),
    ('published', 'Published to store'),
)

INVALID_REASON_CHOICES = (
    ('unexpected-media-type', 'Unexpected media type'),
    ('non-targetable-host', 'Pingbacks not accepted for the given target'),
    ('unsupported-source-scheme', 'Source URL had an unsupported scheme'),
    ('no-link-found', "Couldn't find a link from the source to the target"),
    ('invalid-html', 'Could not parse remote document as HTML'),
    ('http-error', 'Could not download remote document'),
)

EXPEDIENCY_LIST_FIELD_CHOICES = (
    ('domain', 'Source domain'),
    ('ip', 'Submitting IP'),
    ('hostname', 'Submitting hostname'),
)

EXPEDIENCY_LIST_ACTION_CHOICES = (
    ('accepted', 'Accept'),
    ('rejected', 'Reject')
)

class InboundPingback(models.Model):
    PROCESS_QUEUE = 'humfrey:pingback:inbound:process-queue'
    ACCEPTED_QUEUE = 'humfrey:pingback:inbound:accepted-queue'

    slug = models.CharField(max_length=40, primary_key=True)
    source = models.URLField()
    target = models.URLField()
    
    store = models.ForeignKey(Store)

    user_agent = models.TextField(blank=True)
    remote_addr = models.GenericIPAddressField()
    user = models.ForeignKey(User, null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    # Serialized as Turtle
    data = models.TextField(blank=True)

    state = models.CharField(max_length=10, choices=STATE_CHOICES, default='new')
    invalid_reason = models.TextField(blank=True, choices=INVALID_REASON_CHOICES)

    @property
    def graph_name(self):
        return rdflib.URIRef(settings.GRAPH_BASE + 'pingback/' + self.slug)

    @staticmethod
    def get_slug(source, target):
        hash = lambda x: hashlib.sha256(x.encode()).hexdigest()
        return hash(hash(source) + hash(target))

    def queue(self):
        self.state, self.invalid_reason = 'queued', ''
        self.save()
        send_task('humfrey.pingback.process_new_pingback', kwargs={'pingback': self})

    def accept(self):
        self.state, self.invalid_reason = 'accepted', ''
        self.save()
        send_task('humfrey.pingback.accept_pingback', kwargs={'pingback': self})

    def reject(self, save=True):
        self.state, self.invalid_reason = 'rejected', ''
        if save:
            self.save()

    def mark_invalid(self, reason, save=True):
        self.state, self.invalid_reason = 'invalid', reason
        self.data = ''
        if save:
            self.save()

    def mark_pending(self, save=True):
        self.state, self.invalid_reason = 'pending', ''
        if save:
            self.save()

    def mark_published(self, save=True):
        self.state, self.invalid_reason = 'published', ''
        if save:
            self.save()

    def save(self, *args, **kwargs):
        self.slug = self.get_slug(self.source, self.target)
        return super(InboundPingback, self).save(*args, **kwargs)

class AutomatedAction(models.Model):
    """Used for white- and blacklisting certain sources of incoming pingbacks"""

    field = models.CharField(max_length=8, choices=EXPEDIENCY_LIST_FIELD_CHOICES)
    value = models.CharField(max_length=128)

    action = models.CharField(max_length=8, choices=EXPEDIENCY_LIST_ACTION_CHOICES)
