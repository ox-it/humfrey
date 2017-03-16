from django.core.management import BaseCommand, CommandParser
from humfrey.elasticsearch.models import Index

from humfrey.update.models import UpdateDefinition


class Command(BaseCommand):
    def add_arguments(self, parser):
        assert isinstance(parser, CommandParser)

    def handle(self, **opts):
        indexes = Index.objects.all()
        for index in indexes:
            index.update_mapping = True
            index.queue()
