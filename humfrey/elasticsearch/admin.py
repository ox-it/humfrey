from django.contrib import admin

from .models import Index

def queue_index(modeladmin, request, queryset):
    for index in queryset:
        index.queue()
queue_index.short_description = "Queue index"



class IndexAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title', 'status', 'last_queued', 'last_started', 'last_completed', 'item_count')
    list_filter = ('status',)
    actions = [queue_index]


admin.site.register(Index, IndexAdmin)
