import filecmp
import os
import re
import shutil
import subprocess
import tempfile
import urllib
import urllib2

from django.conf import settings
from django_longliving.decorators import pubsub_watcher
import pytz

try:
    from rdflib.plugins.parsers.ntriples import NTriplesParser # 3.0
except ImportError:
    from rdflib.syntax.parsers.ntriples import NTriplesParser # 2.4

from humfrey.update.longliving.updater import Updater
from humfrey.utils.namespaces import NS
from humfrey.sparql.endpoint import Endpoint
from humfrey.streaming.ntriples import NTriplesSource
from humfrey.streaming.rdfxml import RDFXMLSink

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




@pubsub_watcher(channel=Updater.UPDATED_CHANNEL, priority=90)
def update_dataset_archives(channel, data):
    if not getattr(settings, 'ARCHIVE_PATH', None):
        return

    updated = data['updated'].replace(microsecond=0)

    endpoint = Endpoint(settings.ENDPOINT_QUERY)

    query = "SELECT ?dataset WHERE { %s }" % " UNION ".join("{ %s void:inDataset ?dataset }" % g.n3() for s, g in data['graphs'] if s is None)
    datasets = set(r['dataset'] for r in endpoint.query(query))

    for dataset in datasets:
        query = "SELECT ?graph WHERE { ?graph void:inDataset %s }" % dataset.n3()
        graphs = set(r['graph'] for r in endpoint.query(query))
        update_dataset_archive(dataset, graphs, updated)

def update_dataset_archive(dataset, graphs, updated):
    dataset_id = dataset.rsplit('/', 1)[1]

    archive_path = os.path.join(settings.ARCHIVE_PATH, dataset_id)

    if not os.path.exists(archive_path):
        os.makedirs(archive_path, 0755)

    nt_fd, nt_name = tempfile.mkstemp('.nt')
    rdf_fd, rdf_name = tempfile.mkstemp('.rdf')
    try:
        nt_out, rdf_out = os.fdopen(nt_fd, 'w'), os.fdopen(rdf_fd, 'w')
        for graph in graphs:
            _graph_triples(nt_out, graph)
        nt_out.close()

        sort = subprocess.Popen(['sort', '-u', nt_name], stdout=subprocess.PIPE)

        with open(rdf_out, 'w') as sink:
            RDFXMLSink(NTriplesSource(sort.stdout)).serialize(sink)
        sort.wait()
        rdf_out.close()

        previous_name = os.path.join(archive_path, 'latest.rdf')
        if not os.path.exists(previous_name) or not filecmp._do_cmp(previous_name, rdf_name):
            new_name = os.path.join(archive_path,
                                    updated.astimezone(pytz.utc).isoformat() + '.rdf')
            shutil.move(rdf_name, new_name)
            os.chmod(new_name, 0644)
            if os.path.exists(previous_name):
                os.unlink(previous_name)
            os.symlink(new_name, previous_name)


    finally:
        os.unlink(nt_name)
        if os.path.exists(rdf_name):
            os.unlink(rdf_name)
