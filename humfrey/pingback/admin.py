from django.contrib import admin

from .models import InboundPingback

def queue_pingback(modeladmin, request, queryset):
    for pingback in queryset:
        if pingback.state not in ('queued', 'processing'):
            pingback.queue()
queue_pingback.short_description = "Queue pingback for processing"

def accept_pingback(modeladmin, request, queryset):
    for pingback in queryset:
        if pingback.state == 'pending':
            pingback.accept()
accept_pingback.short_description = "Accept pingback"

def reject_pingback(modeladmin, request, queryset):
    for pingback in queryset:
        if pingback.state == 'pending':
            pingback.reject()
reject_pingback.short_description = "Reject pingback"



class InboundPingbackAdmin(admin.ModelAdmin):
    list_display = ('source', 'target', 'state', 'invalid_reason', 'remote_addr', 'created', 'updated')
    list_filter = ('state', 'invalid_reason')
    actions = [queue_pingback, accept_pingback, reject_pingback]

admin.site.register(InboundPingback, InboundPingbackAdmin)
