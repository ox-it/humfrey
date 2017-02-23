

import hashlib
import os
import re
import urllib.request, urllib.parse, urllib.error

import rdflib
from PIL import Image

from django.shortcuts import get_object_or_404
from django.conf import settings
from django.http import HttpResponse, Http404
from django.views.generic import View
from django_conneg.http import HttpBadRequest

from humfrey.utils.namespaces import expand
from humfrey.sparql.models import Store
from humfrey.sparql.views import StoreView

from .encoding import encode_parameters

IMAGE_TYPES = set(map(expand, getattr(settings, 'IMAGE_TYPES', ('foaf:depiction',))))

class ThumbnailView(StoreView):
    image_types = IMAGE_TYPES
    
    @property
    def store(self):
        if not hasattr(self, '_store'):
            store_slug = self.request.GET.get('store', settings.DEFAULT_STORE)
            self._store = get_object_or_404(Store, slug=store_slug)
        return self._store

    def get(self, request):
        if 's' not in request.GET and not request.user.has_perm('sparql.query_store', self.store):
            raise Http404

        try:
            url = rdflib.URIRef(request.GET['url'])
        except KeyError:
            raise Http404

        try:
            width = int(request.GET.get('width'))
        except (ValueError, TypeError):
            width = None
        try:
            height = int(request.GET.get('height'))
        except (ValueError, TypeError):
            height = None
        if not (width or height):
            raise Http404
        
        if 's' in request.GET:
            if request.META['QUERY_STRING'] != encode_parameters(url, width, height):
                raise HttpBadRequest("Invalid s parameter")
        elif not self.image_types & self.get_types(url):
                raise Http404

        filename = hashlib.sha1('{}:{}:{}'.format(width, height, url).encode()).hexdigest()
        filename = [filename[:2], filename[2:4], filename[4:6], filename[6:]]
        filename = os.path.abspath(os.path.join(settings.IMAGE_CACHE_DIRECTORY, *filename))

        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        if not os.path.exists(filename) or os.stat(filename).st_size == 0:
            open(filename, 'w').close()
            temporary_filename, _ = urllib.request.urlretrieve(url)
            try:
                try:
                    im = Image.open(temporary_filename)
                except Exception:
                    raise Http404
                size = im.size

                factor = 1
                if width and width < size[0]:
                    factor = width / size[0]
                if height and height < size[1]:
                    factor = min(factor, height / size[1])

                if factor == 1:
                    resized = im
                else:
                    resized = im.resize((int(size[0] * factor), int(size[1] * factor)), Image.ANTIALIAS)

                if resized.mode != "RGB":
                    resized = im.convert("RGB")
                resized.save(filename, format='jpeg')
            except Exception:
                os.unlink(filename)
                raise
            finally:
                os.unlink(temporary_filename)

        if settings.DEBUG:
            return HttpResponse(open(filename), mimetype='image/jpeg')
        else:
            response = HttpResponse('', mimetype='image/jpeg')
            response['X-SendFile'] = filename
            return response
