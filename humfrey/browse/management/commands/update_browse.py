from django_longliving.util import get_redis_client
from django.core.management.base import BaseCommand
from django.conf import settings

from humfrey.browse import update


class Command(BaseCommand):

    def handle(self, *args, **options):
        client = get_redis_client()

        for browse_list in settings.BROWSE_LISTS:
            update.update_list(client, browse_list)

if __name__ == '__main__':
    import sys
    Command().handle(*sys.argv[1:])
