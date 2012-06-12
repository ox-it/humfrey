from __future__ import division

import hashlib
import os
import re
import urllib

import rdflib
from PIL import Image

from django.conf import settings
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.views.generic import View

from humfrey.utils.namespaces import expand

from .encoding import encode_parameters

IMAGE_TYPES = set(map(expand, getattr(settings, 'IMAGE_TYPES', ('foaf:depiction',))))

class ThumbnailView(View):
    _image_types = IMAGE_TYPES
    def get(self, request):
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
        
        if request.META['QUERY_STRING'] != encode_parameters(url, width, height):
            return HttpResponseBadRequest()

        filename = hashlib.sha1('%s:%s:%s' % (width, height, url)).hexdigest()
        filename = [filename[:2], filename[2:4], filename[4:6], filename[6:]]
        filename = os.path.abspath(os.path.join(settings.IMAGE_CACHE_DIRECTORY, *filename))

        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        if not os.path.exists(filename):
            open(filename, 'w').close()
            if re.match(r"http://www\.mae\.u-paris10\.fr/limc-france/images/.*\.JPG", url):
                url = url[:-4] + '.jpg'
            temporary_filename, _ = urllib.urlretrieve(url)
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
