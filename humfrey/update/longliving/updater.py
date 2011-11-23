import contextlib
import datetime
import logging
import os
import shutil
import tempfile
import urlparse

import dulwich
import pytz

from django.conf import settings

from django_longliving.base import LonglivingThread
from humfrey.update.models import UpdateDefinition
from humfrey.update.transform.base import TransformManager
from humfrey.update.utils import evaluate_pipeline

logger = logging.getLogger(__name__)

class Updater(LonglivingThread):
    UPDATED_CHANNEL = 'humfrey:updater:updated-channel'

    time_zone = pytz.timezone(settings.TIME_ZONE)

    def run(self):
        client = self.get_redis_client()

        for _, update_log in self.watch_queue(client, UpdateDefinition.UPDATE_QUEUE, True):
            logger.info("Item received: %r" % update_log.update_definition.slug)
            try:
                with self.logged(update_log):
                    self.process_item(client, update_log)
            except Exception:
                logger.exception("Exception when processing item")
            logger.info("Item processed: %r" % update_log.update_definition.slug)

    @contextlib.contextmanager
    def logged(self, update_log):
        update_log.started = datetime.datetime.now()
        update_log.save()
        UpdateDefinition.objects \
                        .filter(slug=update_log.update_definition.slug) \
                        .update(status='active', last_started=update_log.started)

        try:
            yield
        finally:
            update_log.completed = datetime.datetime.now()
            update_log.save()
            UpdateDefinition.objects \
                            .filter(slug=update_log.update_definition.slug) \
                            .update(status='idle', last_completed=update_log.completed)

    def process_item(self, client, update_log):

        update_directory = getattr(settings, 'UPDATE_CACHE_DIRECTORY', None)
        if update_directory:
            self._git_pull(settings.UPDATE_TRANSFORM_REPOSITORY, settings.UPDATE_CACHE_DIRECTORY)

        graphs_touched = set()

        variables = update_log.update_definition.variables.all()
        variables = dict((v.name, v.value) for v in variables)

        for pipeline in update_log.update_definition.pipelines.all():
            output_directory = tempfile.mkdtemp()
            transform_manager = TransformManager(update_directory, output_directory, variables)

            try:
                pipeline = evaluate_pipeline(pipeline.value.strip())
            except SyntaxError:
                raise ValueError("Couldn't parse the given pipeline: %r" % pipeline.text.strip())

            try:
                pipeline(transform_manager)
            finally:
                shutil.rmtree(output_directory)

            graphs_touched |= transform_manager.graphs_touched

        updated = self.time_zone.localize(datetime.datetime.now())

        client.publish(self.UPDATED_CHANNEL,
                       self.pack({'slug': update_log.update_definition.slug,
                                  'graphs': graphs_touched,
                                  'updated': updated}))


    def _git_pull(self, git_url, target):
        if not os.path.exists(target):
            os.makedirs(target)
        try:
            repo = dulwich.repo.Repo(target)
        except dulwich.repo.NotGitRepository:
            repo = dulwich.repo.Repo.init(target)

        remote_refs = self._git_fetch(git_url, repo)
        print remote_refs
        try:
            repo.refs['HEAD'] = remote_refs['HEAD']
        except KeyError:
            raise AssertionError("Update transform repository (%s) is empty." % git_url)
        self._git_checkout(repo)

    def _git_fetch(self, git_url, repo):
        client, path = dulwich.client.get_transport_and_path(git_url)
        remote_refs = client.fetch(path, repo)
        return remote_refs

    def _git_checkout(self, repo):
        tree_id = repo['HEAD'].tree
        paths = set()
        for entry in repo.object_store.iter_tree_contents(tree_id):
            path = os.path.join(repo.path, entry.path)
            paths.add(path)
            dirname = os.path.dirname(path)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            with open(path, 'w') as f:
                f.write(repo.get_object(entry.sha).as_raw_string())
            os.chmod(path, entry.mode)

        for base, dirs, files in os.walk(repo.path, topdown=False):
            if not base and '.git' in dirs:
                dirs.remove('.git')
            for path in list(files):
                path = os.path.join(base, path)
                if not path in paths:
                    os.unlink(path)
            if not os.listdir(base):
                os.rmdir(base)
