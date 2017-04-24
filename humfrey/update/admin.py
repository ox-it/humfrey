from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from .models import UpdateDefinition, UpdatePipeline, UpdateLog, Credential


class CredentialAdmin(admin.ModelAdmin):
    list_display = ('user', 'url', 'username')

admin.site.register(Credential, CredentialAdmin)


def queue_update(modeladmin, request, queryset):
    for update_definition in queryset:
        update_definition.queue(trigger='admin', user=request.user)
queue_update.short_description = "Queue update"


class UpdateDefinitionAdmin(GuardedModelAdmin):
    list_display = ('slug', 'title', 'owner', 'cron_schedule', 'status', 'last_queued', 'last_started',
                    'last_completed')
    list_filter = ('status', 'owner')
    actions = [queue_update]

admin.site.register(UpdateDefinition, UpdateDefinitionAdmin)

admin.site.register(UpdatePipeline)
admin.site.register(UpdateLog)