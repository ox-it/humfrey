import datetime
import filecmp
import hashlib
import itertools
import logging
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from celery import shared_task
import dateutil.parser
from django.conf import settings
import rdflib
import pytz

from humfrey.utils.namespaces import NS, expand, HUMFREY
from humfrey.sparql.endpoint import Endpoint
from humfrey.sparql.utils import get_labels, label_predicates
from humfrey.streaming import parse, serialize
from humfrey.update.uploader import Uploader
from humfrey.signals import update_completed

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
        results = self.endpoint.query(query)
        if results:
            return results[0].created
        else:
            return rdflib.Literal(self.updated)

    def _graph_triples(self, out, graph_name):
        url = '%s?%s' % (self.store.graph_store_endpoint,
                         urllib.parse.urlencode({'graph': graph_name}))
        request = urllib.request.Request(url)
        request.add_header('Accept', 'text/plain')
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.warning("Graph not found: %s", graph_name)
            else:
                logger.exception("HTTPError %d for %s: %s", e.code, graph_name, e.read())
            return
        while True:
            chunk = response.read(4096)
            if not chunk:
                break
            out.write(chunk)
    
    def _get_metadata(self, document_uri, document_with_labels_uri, graph_name):
        metadata = rdflib.ConjunctiveGraph()
        metadata += [
            # Use a relative reference (to the current document) in the dump file.
            (self.dataset, NS.void.dataDump, document_uri),
            (self.dataset, HUMFREY.dataDumpWithLabels, document_with_labels_uri),
            (document_uri, NS.rdf.type, NS.foaf.Document),
            (document_uri, NS.dc['format'], rdflib.Literal('application/rdf+xml')),
            (document_uri, NS.dcterms.modified, rdflib.Literal(self.updated)),
            (graph_name, NS.rdf.type, NS.sd.Graph),
            (graph_name, NS.void.inDataset, self.dataset),
            (graph_name, NS.dcterms.modified, rdflib.Literal(self.updated)),
            (graph_name, NS.dcterms.created, self._graph_created(graph_name)),
        ]
        return metadata

    def with_labels(self, triples):
        subjects = set()
        already_labelled = set()
        for s, p, o in triples:
            yield s, p, o
            if p in label_predicates:
                already_labelled.add(s)
            if isinstance(s, rdflib.URIRef):
                subjects.add(s)
            if isinstance(o, rdflib.URIRef):
                subjects.add(o)
        for triple in get_labels(subjects - already_labelled, self.endpoint, mapping=False):
            yield triple

    def archive(self):
        notation = self.notation or hashlib.sha1(self.dataset).hexdigest()

        archive_path = os.path.join(SOURCE_DIRECTORY, 'archive', self.store.slug, notation.replace('/', '-'))
        archive_graph_name = rdflib.URIRef('{0}archive/{1}'.format(settings.GRAPH_BASE, notation))
        data_dump_url = rdflib.URIRef('{0}archive/{1}/{2}/latest.rdf'.format(SOURCE_URL, self.store.slug, notation.replace('/', '-')))
        data_dump_with_labels_url = rdflib.URIRef('{0}archive/{1}/{2}/latest-with-labels.rdf'.format(SOURCE_URL, self.store.slug, notation.replace('/', '-')))

        if not os.path.exists(archive_path):
            os.makedirs(archive_path, 0o755)

        nt_fd, nt_name = tempfile.mkstemp('.nt')
        rdf_fd, rdf_name = tempfile.mkstemp('.rdf')
        rdf_with_labels_fd, rdf_with_labels_name = tempfile.mkstemp('.rdf')
        try:
            nt_out, rdf_out = os.fdopen(nt_fd, 'w'), os.fdopen(rdf_fd, 'w')
            rdf_with_labels_out = os.fdopen(rdf_with_labels_fd, 'w')
            for graph_name in self.graph_names:
                self._graph_triples(nt_out, graph_name)
            nt_out.close()

            with tempfile.TemporaryFile() as sorted_triples:
                subprocess.call(['sort', '-u', nt_name], stdout=sorted_triples)

                sorted_triples.seek(0)
                triples = itertools.chain(self._get_metadata(rdflib.URIRef(''),
                                                             data_dump_with_labels_url,
                                                             archive_graph_name),
                                          parse(sorted_triples, 'nt').get_triples())
                serialize(triples, rdf_out, 'rdf')
                rdf_out.close()

                sorted_triples.seek(0)
                triples = itertools.chain(self._get_metadata(rdflib.URIRef(''),
                                                             data_dump_with_labels_url,
                                                             archive_graph_name),
                                          self.with_labels(parse(sorted_triples, 'nt').get_triples()))
                serialize(triples, rdf_with_labels_out, 'rdf')
                rdf_with_labels_out.close()

            previous_name = os.path.join(archive_path, 'latest.rdf')
            # Only update if the file has changed, or hasn't been archived before.
            if not os.path.exists(previous_name) or not filecmp._do_cmp(previous_name, rdf_name):
                new_name = os.path.join(archive_path,
                                        self.updated.astimezone(pytz.utc).isoformat() + '.rdf')
                shutil.move(rdf_name, new_name)
                os.chmod(new_name, 0o644)
                if os.path.exists(previous_name):
                    os.unlink(previous_name)
                os.symlink(new_name, previous_name)

                new_with_labels_name = os.path.join(archive_path, 'latest-with-labels.rdf')
                shutil.move(rdf_with_labels_name, new_with_labels_name)
                os.chmod(new_with_labels_name, 0o644)

                # Upload the metadata to the store using an absolute URI.
                metadata = self._get_metadata(data_dump_url, data_dump_with_labels_url, archive_graph_name)
                Uploader.upload([self.store], archive_graph_name, graph=metadata)
        finally:
            os.unlink(nt_name)
            if os.path.exists(rdf_name):
                os.unlink(rdf_name)
            self.filter_old_archives(archive_path)

    @classmethod
    def filter_old_archives(cls, archive_path):
        """
        Aims for progressively fewer archives as one goes back in time, to save disk.

        Every archive for today and yesterday, one per day until the beginning
        of the previous month, one per month until the beginning of the
        previous year, and then one per year.
        """

        today = pytz.utc.localize(datetime.datetime.utcnow())
        today = today.replace(hour=0, minute=0, second=0, microsecond=0)

        # limit is the point in time at which we no longer archive at this
        # frequency. epoch is an function that maps a datetime to its
        # partition (such that g(x,y) = f(x) == f(y) is an equivalence
        # relation). We then remove all archives that are in the same
        # partition as the timestamp before it.
        limits = [{'name': 'all',
                   'epoch': lambda dt: dt,
                   'limit': today - datetime.timedelta(1)},
                  {'name': 'daily',
                   'epoch': lambda dt: dt.replace(hour=0, minute=0, second=0, microsecond=0),
                   'limit': today.replace(day=1) - datetime.timedelta(today.isoweekday() % 7 - 7)},
                  {'name': 'weekly',
                   'epoch': lambda dt: dt.replace(hour=0, minute=0, second=0, microsecond=0)
                                       - datetime.timedelta(dt.isoweekday() % 7),
                   'limit': today - datetime.timedelta(28 + today.isoweekday() % 7)},
                  {'name': 'monthly',
                   'epoch': lambda dt: dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                   'limit': today.replace(year=today.year-1, month=1, day=1)},
                  {'name': 'yearly',
                   'epoch': lambda dt: dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                   'limit': pytz.utc.localize(datetime.datetime(1970, 1, 1))}]

        timestamps = []
        for filename in os.listdir(archive_path):
            dt, _ = os.path.splitext(filename)
            try:
                timestamp = dateutil.parser.parse(dt)
            except (TypeError, ValueError):
                continue
            timestamps.append((timestamp, os.path.join(archive_path, filename)))
        timestamps.sort()

        # Always leave the first and last.
        if len(timestamps) < 2:
            return

        # Never delete the last archive
        timestamps.pop()

        last_timestamp = timestamps.pop(0)[0]
        for timestamp, filename in list(timestamps):
            for limit in limits:
                if timestamp < limit['limit']:
                    # The limit doesn't apply as this archive is too far in
                    # the past.
                    continue
                if limit['epoch'](last_timestamp) == limit['epoch'](timestamp):
                    # The archive is in the same partition as the one before
                    # it, and is therefore unnecessary.
                    try:
                        os.unlink(filename)
                    except OSError:
                        logger.exception("Couldn't find file to delete")
                break
            last_timestamp = timestamp

@shared_task(name='humfrey.archive.update_dataset_archives', ignore_result=True)
def update_dataset_archives(sender, update_definition, store_graphs, when, **kwargs):
    for store in store_graphs:
        graph_names = store_graphs[store]
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

        logger.debug("Found %d datasets to archive", len(datasets))
        for dataset in datasets:
            logger.debug("Archiving dataset: %s", dataset)
            notation = datasets[dataset]
            archiver = DatasetArchiver(store, dataset, notation, when)
            archiver.archive()

update_completed.connect(update_dataset_archives.delay)
