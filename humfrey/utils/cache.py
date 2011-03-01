import pickle, base64

from django.core.cache import cache

def cached_view(view):
    view.cached = True
    return view
