import mock

def stub_reverse_full(host, url):
    if (host, url) == ('data', 'doc-generic'):
        return '//data.example.org/doc/'
    elif (host, url) == ('data', 'desc'):
        return '//data.example.org/desc/'
    else:
        raise AssertionError("reverse_full called with unexpected arguments.")


TEST_ID_MAPPING = (
    ('http://random.example.org/id/', 'http://data.example.org/doc:random/', False),
    ('http://id.example.org/', 'http://data.example.org/doc/', True)
)

def patch_id_mapping(f):
    f = mock.patch('django.conf.settings.ID_MAPPING', TEST_ID_MAPPING, create=True)(f)
    f = mock.patch('humfrey.linkeddata.uri.reverse_full', stub_reverse_full, create=True)(f)
    return f