from django_hosts.reverse import reverse_crossdomain

class PingbackMiddleware(object):
	def process_response(self, request, response):
		response['X-Pingback'] = request.build_absolute_uri(reverse_crossdomain('data', 'pingback:xmlrpc'))
		return response
