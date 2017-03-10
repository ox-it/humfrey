from django.core.management import BaseCommand, CommandParser

from humfrey.update.models import UpdateDefinition


class Command(BaseCommand):
    def add_arguments(self, parser):
        assert isinstance(parser, CommandParser)
        parser.add_argument('slug')
        parser.add_argument('-f', '--force', action='store_true', dest='force')

    def handle(self, **opts):
        update_definition = UpdateDefinition.objects.get(slug=opts['slug'])
        if opts.get('force') and update_definition.status == 'queued':
            update_definition.status = 'idle'
        update_definition.queue(trigger='command', forced=opts.get('force', False))
