import itertools
import os

from lxml import etree

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files import File

from humfrey.update.models import UpdateDefinition, UpdatePipeline, LocalFile

class Command(BaseCommand):
    def handle(self, *args, **options):
        path = args[0]

        definition_filename = os.path.join(path, 'meta.xml')
        with open(definition_filename, 'r') as f:
            meta = etree.parse(definition_filename)

        owner = meta.xpath('/meta/owner')[0].text

        for definition in meta.xpath('/meta/definition'):
            self.import_definition(definition, owner)

        for filename in os.listdir(path):
            if filename == 'meta.xml' or filename.startswith('.'):
                continue
            local_file, _ = LocalFile.objects.get_or_create(name=filename)
            if local_file.content:
                local_file.content.delete()
            with open(os.path.join(path, filename)) as src:
                local_file.content.save(filename, File(src))
            print local_file.content.file.name

    def import_definition(self, meta, default_owner):
        slug = meta.xpath('slug')[0].text

        try:
            definition = UpdateDefinition.objects.get(slug=slug)
        except UpdateDefinition.DoesNotExist:
            definition = UpdateDefinition(slug=slug)

        for name in ('title', 'description', 'cron_schedule'):
            field = meta.xpath(name)
            setattr(definition, name, field[0].text if field else '')

        owner = meta.xpath('owner')
        owner = owner[0].text if owner else default_owner
        definition.owner = User.objects.get(username=owner)

        definition.save()

        # Update pipelines
        current = definition.pipelines.all()
        desired = [p.text for p in meta.xpath('pipelines/pipeline')]
        for obj, value in itertools.izip_longest(current, desired):
            if not obj:
                obj = UpdatePipeline(update_definition=definition)
            if value:
                obj.value = value
                obj.save()
            else:
                obj.delete()

