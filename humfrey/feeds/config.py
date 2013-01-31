from django.conf import settings
from django.utils.importlib import import_module

FEEDS = getattr(settings, 'HUMFREY_FEEDS', {}).copy()
FEED_META = {}
for slug in list(FEEDS):
    mod_name, class_name = FEEDS[slug].rsplit('.', 1)
    feed = getattr(import_module(mod_name),
                               class_name)
    meta = {'slug': slug,
            'name': feed.name,
            'plural_name': feed.plural_name,
            'description': feed.description}
    FEEDS[slug] = feed.as_view(slug=slug, meta=meta)
    FEED_META[slug] = meta

del mod_name, class_name, slug, feed, meta