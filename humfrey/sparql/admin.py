from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from .models import Store, UserPrivileges

class StoreAdmin(GuardedModelAdmin):
    list_display = ('slug', 'name')

admin.site.register(Store, StoreAdmin)
admin.site.register(UserPrivileges)