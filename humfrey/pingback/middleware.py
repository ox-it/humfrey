from django_hosts import reverse


class PingbackMiddleware(object):
	def process_response(self, request, response):
		response['X-Pingback'] = request.build_absolute_uri(reverse('pingback:xmlrpc', host='data'))
		return response
