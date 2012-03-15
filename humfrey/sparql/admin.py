from django.contrib import admin

from .models import Store, UserPrivileges

class StoreAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name')

admin.site.register(Store, StoreAdmin)
admin.site.register(UserPrivileges)