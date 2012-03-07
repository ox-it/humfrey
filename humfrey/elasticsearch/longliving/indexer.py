from datetime import datetime
import logging

from django_longliving.base import LonglivingThread

from humfrey.elasticsearch.models import Index
from humfrey.elasticsearch.update import IndexUpdater

logger = logging.getLogger(__name__)

class Indexer(LonglivingThread):
    def run(self):
        client = self.get_redis_client()
        for _, index in self.watch_queue(client, Index.UPDATE_QUEUE, True):
            try:
                index.status = 'active'
                index.last_started = datetime.now()
                index.save()
                self.process_index(index)
            except Exception, e:
                logger.exception("Failed to process index")
            finally:
                index.status = 'idle'
                index.last_completed = datetime.now()
                index.save()

    def process_index(self, index):
        updater = IndexUpdater()
        index.item_count = updater.update(index)
