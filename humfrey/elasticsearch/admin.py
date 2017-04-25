try:
    import simplejson
except ImportError:
    import json

from django.contrib import admin
from django import forms

from .models import Index


def queue_index(modeladmin, request, queryset):
    for index in queryset:
        index.queue()
queue_index.short_description = "Queue index"


class IndexAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title', 'status', 'last_queued', 'last_started', 'last_completed', 'item_count', 'get_duration')
    list_filter = ('status',)
    actions = [queue_index]

    def get_duration(self, index):
        if index.last_started and index.last_completed and index.last_started < index.last_completed:
            return (index.last_completed - index.last_started).total_seconds()
        return ''
    get_duration.short_description = 'duration'

admin.site.register(Index, IndexAdmin)
