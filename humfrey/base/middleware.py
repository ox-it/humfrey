class AccessControlAllowOriginMiddleware(object):
    """
    Implements the Access-Control-Allow-Origin: * header, as per
    https://developer.mozilla.org/En/HTTP_access_control#Access-Control-Allow-Origin
    in order that JS-based clients can perform requests against this site
    unhindered.
    """

    def process_response(self, request, response):
        response['Access-Control-Allow-Origin'] = request.META.get('HTTP_ORIGIN', '*')
        response['Access-Control-Expose-Headers'] = 'WWW-Authenticate'
        if request.method == 'OPTIONS':
            allow_methods = response.get('Accept', request.META.get('HTTP_ACCESS_CONTROL_REQUEST_METHOD'))
            if allow_methods:
                response['Access-Control-Allow-Methods'] = allow_methods
            allow_headers = request.META.get('HTTP_ACCESS_CONTROL_REQUEST_HEADERS')
            if allow_headers:
                response['Access-Control-Allow-Headers'] = allow_headers
        
        return response