class AccessControlAllowOriginMiddleware(object):
    """
    Implements the Access-Control-Allow-Origin: * header, as per
    https://developer.mozilla.org/En/HTTP_access_control#Access-Control-Allow-Origin
    in order that JS-based clients can perform requests against this site
    unhindered.
    """

    def process_response(self, request, response):
        response['Access-Control-Allow-Origin'] = '*'
        return response