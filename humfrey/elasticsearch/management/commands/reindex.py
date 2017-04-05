import datetime

from django.core.management import BaseCommand, CommandParser
from humfrey.elasticsearch.models import Index


class Command(BaseCommand):
    def add_arguments(self, parser):
        assert isinstance(parser, CommandParser)
        parser.add_argument('-d', '--direct', action='store_true', dest='direct')

    def handle(self, **opts):
        indexes = Index.objects.all()
        for index in indexes:
            if opts.get('direct'):
                index.status = 'queued'
                index.last_queued = datetime.datetime.now()
                index.save()

                from ... import tasks
                tasks.update_index(index_id=index.pk)
            else:
                index.update_mapping = True
                index.queue()
