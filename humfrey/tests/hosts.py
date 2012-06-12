from django_hosts import patterns, host

host_patterns = patterns('',
    host(r'^data.example.org$', 'humfrey.tests.urls.main', name='data'),
    host(r'$x^', 'humfrey.tests.urls.empty', name='empty'),
)

