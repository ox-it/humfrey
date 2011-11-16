from django.contrib.admin import site

from .models import UpdateDefinition, UpdatePipeline

site.register(UpdateDefinition)
site.register(UpdatePipeline)
