from django.core.signals import Signal
from django.dispatch import receiver

__all__ = ['graphs_updated', 'graph_updated',
           'resources_updated', 'resource_updated',
           'update_completed']

# From http://dougalmatthews.com/2011/10/10/making-django%27s-signals-asynchronous-with-celery/
# Prevents celery trying to pickle Signal.lock.
# Warning. Monkey patch.
def reducer(self):
    return (Signal, (self.providing_args,))
Signal.__reduce__ = reducer

graphs_updated = Signal(providing_args=['store', 'graphs', 'when'])
graph_updated = Signal(providing_args=['store', 'graph', 'when'])

resources_updated = Signal(providing_args=['store', 'uris', 'when'])
resource_updated = Signal(providing_args=['store', 'uri', 'when'])

update_completed = Signal(providing_args=['update_definition', 'store_graphs', 'when'])

@receiver(graphs_updated)
def _graphs_updated(sender, store, graphs, when, **kwargs):
    for graph in graphs:
        graph_updated.send(sender, store=store, graph=graph, when=when, **kwargs)

@receiver(resources_updated)
def _resources_updated(sender, store, uris, when, **kwargs):
    for uri in uris:
        resources_updated.send(sender, store=store, uri=uri, when=when, **kwargs)

