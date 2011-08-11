from __future__ import division

import os, hashlib, urllib, re

import rdflib
from PIL import Image

from django.http import HttpResponse, Http404
from django.conf import settings

from humfrey.desc.views import EndpointView
from humfrey.utils.namespaces import expand

class ResizedImageView(EndpointView):
    _image_types = set(map(expand, settings.IMAGE_TYPES))
    def get(self, request):
        try:
            url = rdflib.URIRef(request.GET['url'])
            width = int(request.GET['width'])
            if width not in settings.THUMBNAIL_WIDTHS:
                raise Http404
            types = self.get_types(url)
            if not (types & self._image_types):
                raise TypeError
        except Exception:
            raise
            raise Http404
            
        filename = hashlib.sha1('%d:%s' % (width, url)).hexdigest()
        filename = [filename[:2], filename[2:4], filename[4:6], filename[6:]]
        filename = os.path.abspath(os.path.join(settings.RESIZED_IMAGE_CACHE_DIR, *filename))

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
                ratio = size[1] / size[0]

                if width >= size[0]:
                    resized = im
                else:
                    resized = im.resize((width, int(round(width*ratio))), Image.ANTIALIAS)
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
