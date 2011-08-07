from humfrey.longliving.base import LonglivingThread

class Updater(LonglivingThread):
    QUEUE_NAME = 'updater:queue'

    def run(self):
        client = self.get_redis_client()
        
        for _, item in self.watch_queue(client, self.QUEUE_NAME, True):
            self.process_item(item)
    
    def process_item(self, item):
        pass