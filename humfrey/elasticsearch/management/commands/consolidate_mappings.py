import json
import operator
import pprint

import collections
import datetime

from django.core.management import BaseCommand, CommandParser
from functools import reduce

from humfrey.elasticsearch.models import Index


class Command(BaseCommand):
    help = "Make sure there are no conflicts between ElasticSearch mappings"

    def add_arguments(self, parser):
        assert isinstance(parser, CommandParser)

    def add_field_mappings(self, index_name, field_mappings, mapping, prefix=''):
        for name, field_mapping in mapping.items():
            field_mappings[prefix + name][index_name] = field_mapping
            if 'properties' in field_mapping:
                self.add_field_mappings(index_name, field_mappings, field_mapping.pop('properties'),
                                        prefix=prefix + name + '.')

    def handle(self, **opts):
        indexes = Index.objects.all()
        field_mappings = collections.defaultdict(dict)
        for index in indexes:
            mapping = json.loads(index.mapping)
            self.add_field_mappings(index.pk, field_mappings, mapping[index.pk]['properties'])

        # for k in list(field_mappings):
        #     values = list(field_mappings[k].values())
        #     if all(values[0] == v for v in values[1:]):
        #         del field_mappings[k]

        pprint.pprint(dict(field_mappings))