from django.contrib import admin

from .models import UpdateDefinition, UpdatePipeline, UpdateLog, Credential

class CredentialAdmin(admin.ModelAdmin):
    list_display = ('user', 'url', 'username')

admin.site.register(UpdateDefinition)
admin.site.register(UpdatePipeline)
admin.site.register(UpdateLog)
admin.site.register(Credential, CredentialAdmin)
