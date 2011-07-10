def stub_reverse_crossdomain(host, url):
    if (host, url) == ('data', 'doc-generic'):
        return '//data.example.org/doc/'
    elif (host, url) == ('data', 'desc'):
        return '//data.example.org/desc/'
    else:
        raise AssertionError("reverse_crossdomain called with unexpected arguments.")


