from django.conf import settings
from django.urls import reverse
from django.views.generic import View

from humfrey.linkeddata.mappingconf import set_id_mapping, set_doc_view, set_desc_view, set_resource_registry
from humfrey.linkeddata.resource import base_resource_registry, ResourceRegistry

class MappingView(View):
    id_mapping = getattr(settings, 'ID_MAPPING', ())

    @property
    def doc_view(self):
        return reverse('doc-generic')

    @property
    def desc_view(self):
        return reverse('desc')

    if getattr(settings, 'RESOURCE_REGISTRY', None):
        resource_registry = ResourceRegistry._get_object(settings.RESOURCE_REGISTRY)
    else:
        resource_registry = base_resource_registry

    def dispatch(self, request, *args, **kwargs):
        set_id_mapping(self.id_mapping)
        set_doc_view(self.doc_view)
        set_desc_view(self.desc_view)
        set_resource_registry(self.resource_registry)
        try:
            return super(MappingView, self).dispatch(request, *args, **kwargs)
        finally:
            set_id_mapping(None)
            set_doc_view(None)
            set_desc_view(None)
            set_resource_registry(None)
