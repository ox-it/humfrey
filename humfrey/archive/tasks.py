import filecmp
import os
import re
import shutil
import subprocess
import tempfile
import urllib
import urllib2

from celery.task import task
from django.conf import settings
import pytz

try:
    from rdflib.plugins.parsers.ntriples import NTriplesParser # 3.0
except ImportError:
    from rdflib.syntax.parsers.ntriples import NTriplesParser # 2.4

from humfrey.utils.namespaces import NS
from humfrey.sparql.models import Store
from humfrey.sparql.endpoint import Endpoint
from humfrey.streaming.ntriples import NTriplesSource
from humfrey.streaming.rdfxml import RDFXMLSink

def _graph_triples(out, store, graph):
    url = '%s?%s' % (store.graph_store_endpoint,
                     urllib.urlencode({'graph': graph}))
    request = urllib2.Request(url)
    request.add_header('Accept', 'text/plain')

    response = urllib2.urlopen(request)
    while True:
        chunk = response.read(4096)
        if not chunk:
            break
        out.write(chunk)

@task(name='humfrey.archive.update_dataset_archives')
def update_dataset_archives(update_log, graphs, updated):
    if not getattr(settings, 'ARCHIVE_PATH', None):
        return

    updated = updated.replace(microsecond=0)
    
    for store_slug in graphs:
        store = Store.objects.get(slug=store_slug)
        graph_names = graphs[store.slug]
        endpoint = Endpoint(store.query_endpoint)

        query = "SELECT ?dataset WHERE { %s }" % " UNION ".join("{ %s void:inDataset ?dataset }" % g.n3() for s, g in graph_names if s is None)
        datasets = set(r['dataset'] for r in endpoint.query(query))
    
        for dataset in datasets:
            query = "SELECT ?graph WHERE { ?graph void:inDataset %s }" % dataset.n3()
            graphs = set(r['graph'] for r in endpoint.query(query))
            update_dataset_archive(dataset, store, graph_names, updated)

def update_dataset_archive(dataset, store, graph_names, updated):
    dataset_id = dataset.rsplit('/', 1)[1]

    archive_path = os.path.join(settings.ARCHIVE_PATH, store.slug, dataset_id)

    if not os.path.exists(archive_path):
        os.makedirs(archive_path, 0755)

    nt_fd, nt_name = tempfile.mkstemp('.nt')
    rdf_fd, rdf_name = tempfile.mkstemp('.rdf')
    try:
        nt_out, rdf_out = os.fdopen(nt_fd, 'w'), os.fdopen(rdf_fd, 'w')
        for graph in graph_names:
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
