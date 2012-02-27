import filecmp
import os
import re
import shutil
import subprocess
import tempfile
import urllib
import urllib2
from xml.sax.saxutils import quoteattr, escape

from django.conf import settings
from django_longliving.decorators import pubsub_watcher
import pytz
from rdflib import URIRef, BNode, Literal

try:
    from rdflib.plugins.parsers.ntriples import NTriplesParser # 3.0
except ImportError:
    from rdflib.syntax.parsers.ntriples import NTriplesParser # 2.4

from humfrey.update.longliving.updater import Updater
from humfrey.utils.namespaces import NS

def _graph_triples(out, graph):
    url = '%s?%s' % (settings.ENDPOINT_GRAPH,
                     urllib.urlencode({'graph': graph}))
    request = urllib2.Request(url)
    request.add_header('Accept', 'text/plain')

    response = urllib2.urlopen(request)
    while True:
        chunk = response.read(4096)
        if not chunk:
            break
        out.write(chunk)

class ArchiveSink(object):
    localpart = re.compile(ur'[A-Za-z_][A-Za-z_\d]+$')

    def __init__(self, out, namespaces, encoding='utf-8'):
        self.out = out
        self.encoding = encoding
        self.write = lambda s: out.write(s.encode(encoding))
        self.namespaces = sorted(namespaces.items())
        self.last_subject = None

    def __enter__(self):
        write = self.write
        write(u'<?xml version="1.0" encoding=%s?>\n' % quoteattr(self.encoding))
        write(u'<rdf:RDF')
        for prefix, uri in self.namespaces:
            write(u'\n    xmlns:%s=%s' % (prefix, quoteattr(uri)))
        write(u'>\n')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        write = self.write
        if self.last_subject:
            write(u'  </rdf:Description>\n')
        write(u'</rdf:RDF>\n')

    def triple(self, s, p, o):
        write = self.write
        if s != self.last_subject:
            if self.last_subject:
                write(u'  </rdf:Description>\n')
            self.last_subject = s
            if isinstance(s, URIRef):
                write(u'  <rdf:Description rdf:about=%s>\n' % quoteattr(s))
            else:
                write(u'  <rdf:Description rdf:nodeID=%s>\n' % quoteattr(s))
        for prefix, uri in self.namespaces:
            if p.startswith(uri) and self.localpart.match(p[len(uri):]):
                tag_name = '%s:%s' % (prefix, p[len(uri):])
                write(u'    <%s' % tag_name)
                break
        else:
            match = self.localpart.search(p)
            tag_name = p[match.start:]
            write(u'    <%s xmlns=%s' % (tag_name, quoteattr(p[:match.start])))

        if isinstance(o, Literal):
            if o.language:
                write(u' xml:lang=%s' % quoteattr(o.language))
            if o.datatype:
                write(u' rdf:datatype=%s' % quoteattr(o.datatype))
            write('>%s</%s>\n' % (escape(o), tag_name))
        elif isinstance(o, BNode):
            write(u' rdf:nodeID=%s/>\n' % quoteattr(o))
        else:
            write(u' rdf:resource=%s/>\n' % quoteattr(o))


@pubsub_watcher(channel=Updater.UPDATED_CHANNEL, priority=90)
def update_dataset_archive(channel, data):
    if not getattr(settings, 'ARCHIVE_PATH', None):
        return

    graphs = data['graphs']
    archive_path = os.path.join(settings.ARCHIVE_PATH, data['id'])

    if not os.path.exists(archive_path):
        os.makedirs(archive_path)

    nt_fd, nt_name = tempfile.mkstemp('.nt')
    rdf_fd, rdf_name = tempfile.mkstemp('.rdf')
    try:
        nt_out, rdf_out = os.fdopen(nt_fd, 'w'), os.fdopen(rdf_fd, 'w')
        for graph in graphs:
            _graph_triples(nt_out, graph)
        nt_out.close()

        sort = subprocess.Popen(['sort', '-u', nt_name], stdout=subprocess.PIPE)

        with ArchiveSink(rdf_out, NS) as sink:
            parser = NTriplesParser(sink=sink)
            parser.parse(sort.stdout)
        sort.wait()
        rdf_out.close()

        previous_name = os.path.join(archive_path, 'latest.rdf')
        if not os.path.exists(previous_name) or not filecmp._do_cmp(previous_name, rdf_name):
            new_name = os.path.join(archive_path,
                                    data['updated'].astimezone(pytz.utc).isoformat() + '.rdf')
            shutil.move(rdf_name, new_name)
            if os.path.exists(previous_name):
                os.unlink(previous_name)
            os.symlink(new_name, previous_name)


    finally:
        os.unlink(nt_name)
        if os.path.exists(rdf_name):
            os.unlink(rdf_name)


