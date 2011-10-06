from django_hosts.reverse import reverse_full

class PingbackMiddleware(object):
	def process_response(self, request, response):
		response['X-Pingback'] = request.build_absolute_uri(reverse_full('data', 'pingback:xmlrpc'))
		return response
