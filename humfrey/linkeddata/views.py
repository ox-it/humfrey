from django.conf import settings
from django.views.generic import View

from humfrey.linkeddata.mappingconf import set_id_mapping, set_doc_view, set_desc_view

class MappingView(View):
    id_mapping = getattr(settings, 'ID_MAPPING', ())
    doc_view = ('data', 'doc-generic')
    desc_view = ('data', 'desc')
    
    def dispatch(self, request, *args, **kwargs):
        set_id_mapping(self.id_mapping)
        set_doc_view(self.doc_view)
        set_desc_view(self.desc_view)
        try:
            return super(MappingView, self).dispatch(request, *args, **kwargs)
        finally:
            set_id_mapping(None)
            set_doc_view(None)
            set_desc_view(None)