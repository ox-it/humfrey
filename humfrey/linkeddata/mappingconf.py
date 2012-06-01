import threading

_conf = threading.local()

def get_id_mapping():
    return _conf.id_mapping
def set_id_mapping(value):
    _conf.id_mapping = value

def get_doc_view():
    return _conf.doc_view
def set_doc_view(value):
    _conf.doc_view = value

def get_desc_view():
    return _conf.desc_view
def set_desc_view(value):
    _conf.desc_view = value

def get_resource_registry():
    return _conf.resource_registry
def set_resource_registry(value):
    _conf.resource_registry = value
