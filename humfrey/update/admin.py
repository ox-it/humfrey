from django.contrib.admin import site

from .models import UpdateDefinition, UpdatePipeline, UpdateLog

site.register(UpdateDefinition)
site.register(UpdatePipeline)
site.register(UpdateLog)
