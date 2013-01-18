import functools

from humfrey.linkeddata.resource import Resource
from humfrey.sparql.utils import get_labels
from .core import StoreView

class CannedQueryView(StoreView):
    query = None
    template_name = None
    with_labels = False

    def get_query(self, request, *args, **kwargs):
        return self.query

    def get_locations(self, request, *args, **kwargs):
        """
        Override to provide the canonical and format-specific locations for this resource.
        
        Example return value: ('http://example.com/data', 'http://example.org/data.rss')
        """
        return None, None

    def get_subjects(self, request, result, *args, **kwargs):
        return ()

    def get_additional_context(self, request, *args, **kwargs):
        return {}

    def finalize_context(self, request, context, *args, **kwargs):
        """
        This is passed the context just before it is rendered. Override to add
        items to the context based on what is already there. This method should
        return the context to be rendered.
        """
        return context

    def get(self, request, *args, **kwargs):
        context = self.context
        self.base_location, self.content_location = self.get_locations(request, *args, **kwargs)
        query = self.get_query(request, *args, **kwargs)

        results = self.endpoint.query(query)
        context.update({'results': results,
                        'parsed_results': results.get()})
        if results.get_sparql_results_type() == 'graph':
            graph = context['parsed_results']
            self.resource = functools.partial(Resource, graph=graph, endpoint=self.endpoint)
            subjects = self.get_subjects(request, graph, *args, **kwargs)
            context['subjects'] = map(self.resource, subjects)
            if self.with_labels:
                graph += get_labels(graph, self.endpoint, mapping=False)

        if self.content_location:
            context['additional_headers'] = {'Content-location': self.content_location}

        context.update(self.get_additional_context(request, *args, **kwargs))
        context = self.finalize_context(request, context, *args, **kwargs)

        return self.render()
