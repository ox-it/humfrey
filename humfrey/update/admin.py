from django.contrib import admin
from django import forms
from guardian.admin import GuardedModelAdmin

from .models import UpdateDefinition, UpdatePipeline, UpdateLog, Credential


class CredentialForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)

    def clean_password(self):
        if not self.cleaned_data.get('password') and self.instance:
            return self.instance.password
        elif self.cleaned_data.get('password'):
            return self.cleaned_data['password']

    class Meta:
        model = Credential
        fields = ('user', 'url', 'username', 'password')


class CredentialAdmin(admin.ModelAdmin):
    list_display = ('user', 'url', 'username')
    form = CredentialForm

admin.site.register(Credential, CredentialAdmin)


def queue_update(modeladmin, request, queryset):
    for update_definition in queryset:
        update_definition.queue(trigger='admin', user=request.user, silent=True)
queue_update.short_description = "Queue update"


class UpdateDefinitionAdmin(GuardedModelAdmin):
    list_display = ('slug', 'title', 'owner', 'cron_schedule', 'status', 'last_queued', 'last_started',
                    'last_completed')
    list_filter = ('status',)
    actions = [queue_update]

admin.site.register(UpdateDefinition, UpdateDefinitionAdmin)

admin.site.register(UpdatePipeline)
admin.site.register(UpdateLog)