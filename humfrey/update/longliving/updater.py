from humfrey.longliving.base import LonglivingThread

class Updater(LonglivingThread):
    QUEUE_NAME = 'updater:queue'
