import filecmp
import hashlib
import itertools
import logging
import os
import re
import shutil
import subprocess
import tempfile
import urllib
import urllib2

from celery.task import task
from django.conf import settings
import rdflib
import pytz

try:
    from rdflib.plugins.parsers.ntriples import NTriplesParser # 3.0
except ImportError:
    from rdflib.syntax.parsers.ntriples import NTriplesParser # 2.4

from humfrey.utils.namespaces import NS, expand
from humfrey.sparql.models import Store
from humfrey.sparql.endpoint import Endpoint
from humfrey.streaming.ntriples import NTriplesSource
from humfrey.streaming.rdfxml import RDFXMLSink
from humfrey.update.uploader import Uploader

DATASET_NOTATION = getattr(settings, 'DATASET_NOTATION', None)
if DATASET_NOTATION:
    DATASET_NOTATION = expand(DATASET_NOTATION)

GRAPH_BASE = getattr(settings, 'GRAPH_BASE', None)
SOURCE_DIRECTORY = getattr(settings, 'SOURCE_DIRECTORY', None)
SOURCE_URL = getattr(settings, 'SOURCE_URL', None)

logger = logging.getLogger(__name__)

class DatasetArchiver(object):

    def __init__(self, store, dataset, notation, updated):
        self.store = store
        self.dataset = dataset
        self.notation = notation
        self.updated = updated.replace(microsecond=0)
        self.endpoint = Endpoint(store.query_endpoint)

    @property
    def graph_names(self):
        if not hasattr(self, '_graphs'):
            query = "SELECT ?graph WHERE {{ ?graph void:inDataset/^void:subset* {0} }}".format(self.dataset.n3())
            self._graphs = set(r['graph'] for r in self.endpoint.query(query))
        return self._graphs

    def _graph_created(self, graph_name):
        query = "SELECT ?created WHERE {{ {0} dcterms:created ?created }}".format(graph_name.n3())
        results = self.endpoint.query(query).get()
        if results:
            return results[0].created
        else:
            return rdflib.URIRef(self.updated)

    def _graph_triples(self, out, graph_name):
        url = '%s?%s' % (self.store.graph_store_endpoint,
                         urllib.urlencode({'graph': graph_name}))
        request = urllib2.Request(url)
        request.add_header('Accept', 'text/plain')
        response = urllib2.urlopen(request)
        while True:
            chunk = response.read(4096)
            if not chunk:
                break
            out.write(chunk)
    
    def _get_metadata(self, document_uri, graph_name):
        metadata = rdflib.ConjunctiveGraph()
        metadata += [
            # Use a relative reference (to the current document) in the dump file.
            (self.dataset, NS.void.dataDump, document_uri),
            (document_uri, NS.rdf.type, NS.foaf.Document),
            (document_uri, NS.dc['format'], rdflib.Literal('application/rdf+xml')),
            (document_uri, NS.dcterms.modified, rdflib.Literal(self.updated)),
            (graph_name, NS.rdf.type, NS.sd.Graph),
            (graph_name, NS.void.inDataset, self.dataset),
            (graph_name, NS.dcterms.modified, rdflib.Literal(self.updated)),
            (graph_name, NS.dcterms.created, self._graph_created(graph_name)),
        ]
        return metadata

    def archive(self):
        notation = self.notation or hashlib.sha1(self.dataset).hexdigest()

        archive_path = os.path.join(SOURCE_DIRECTORY, 'archive', self.store.slug, notation.replace('/', '-'))
        graph_name = rdflib.URIRef('{0}archive/{1}'.format(settings.GRAPH_BASE, notation))
        data_dump_url = rdflib.URIRef('{0}archive/{1}/{2}/latest.rdf'.format(SOURCE_URL, self.store.slug, notation.replace('/', '-')))

        if not os.path.exists(archive_path):
            os.makedirs(archive_path, 0755)

        nt_fd, nt_name = tempfile.mkstemp('.nt')
        rdf_fd, rdf_name = tempfile.mkstemp('.rdf')
        try:
            nt_out, rdf_out = os.fdopen(nt_fd, 'w'), os.fdopen(rdf_fd, 'w')
            for graph_name in self.graph_names:
                self._graph_triples(nt_out, graph_name)
            nt_out.close()

            sort = subprocess.Popen(['sort', '-u', nt_name], stdout=subprocess.PIPE)

            # Use a relative reference (to the current document) in the dump file.
            RDFXMLSink(rdf_out, triples=itertools.chain(self._get_metadata(rdflib.URIRef(''), graph_name),
                                                        NTriplesSource(sort.stdout)))
            sort.wait()
            rdf_out.close()

            previous_name = os.path.join(archive_path, 'latest.rdf')
            # Only update if the file has changed, or hasn't been archived before.
            if not os.path.exists(previous_name) or not filecmp._do_cmp(previous_name, rdf_name):
                new_name = os.path.join(archive_path,
                                        self.updated.astimezone(pytz.utc).isoformat() + '.rdf')
                shutil.move(rdf_name, new_name)
                os.chmod(new_name, 0644)
                if os.path.exists(previous_name):
                    os.unlink(previous_name)
                os.symlink(new_name, previous_name)

                # Upload the metadata to the store using an absolute URI.
                metadata = self._get_metadata(data_dump_url, graph_name)
                Uploader.upload([self.store], graph_name, graph=metadata)
        finally:
            os.unlink(nt_name)
            if os.path.exists(rdf_name):
                os.unlink(rdf_name)

@task(name='humfrey.archive.update_dataset_archives')
def update_dataset_archives(update_log, graphs, updated):
    for store_slug in graphs:
        store = Store.objects.get(slug=store_slug)
        graph_names = graphs[store.slug]
        endpoint = Endpoint(store.query_endpoint)

        if DATASET_NOTATION:
            notation_clause = """
                OPTIONAL {{ ?dataset skos:notation ?notation .
                FILTER (DATATYPE(?notation) = {0} ) }}""".format(DATASET_NOTATION.n3())
        else:
            notation_clause = ""

        query = """
        SELECT ?dataset ?notation WHERE {{
          VALUES ?graph {{ {0} }}
          ?graph void:inDataset ?dataset .
          {1}
        }}""".format(" ".join(g.n3() for g in graph_names),
                     notation_clause)
        datasets = dict(endpoint.query(query))

        for dataset in datasets:
            notation = datasets[dataset]
            archiver = DatasetArchiver(store, dataset, notation, updated)
            archiver.archive()

