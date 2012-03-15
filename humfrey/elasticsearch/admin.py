try:
    import json
except ImportError:
    import simplejson

from django.contrib import admin
from django import forms

from .models import Index

def queue_index(modeladmin, request, queryset):
    for index in queryset:
        index.queue()
queue_index.short_description = "Queue index"

class IndexAdminForm(forms.ModelForm):
    slug = forms.RegexField(regex=r'^[a-z\-]+_[a-z\-]+$')

    class Meta:
        model = Index

    def clean_mapping(self):
        if not self.cleaned_data.get('mapping'):
            return
        try:
            json.loads(self.cleaned_data['mapping'])
        except ValueError, e:
            raise forms.ValidationError(e)

class IndexAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title', 'status', 'last_queued', 'last_started', 'last_completed', 'item_count')
    list_filter = ('status',)
    actions = [queue_index]


admin.site.register(Index, IndexAdmin)
