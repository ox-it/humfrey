import functools

from django_conneg.decorators import renderer

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

    def get_subjects(self, graph):
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

        context['results'] = self.endpoint.query(query)
        context.update(self.get_additional_context(request, *args, **kwargs))
        context = self.finalize_context(request, context, *args, **kwargs)

        return self.render()

    def undefer(self):
        context = self.context
        results = context.pop('results', False)
        if not results:
            return
        sparql_results_type = results.get_sparql_results_type()
        context['sparql_results_type'] = sparql_results_type
        context[sparql_results_type] = results.get()
        if sparql_results_type == 'resultset':
            context['fields'] = results.get_fields()
        elif sparql_results_type == 'graph':
            graph = context['graph']
            self.resource = functools.partial(Resource, graph=graph, endpoint=self.endpoint)
            subjects = self.get_subjects(graph)
            context['subjects'] = map(self.resource, subjects)

    def render_html_test(self, request, context, template_name):
        return hasattr(super(CannedQueryView, self), 'render_html')

    @renderer(format='html', mimetypes=('application/xhtml+xml', 'text/html'), name='HTML', test=render_html_test)
    def render_html(self, request, context, template_name):
        self.undefer()
        return super(CannedQueryView, self).render_html(request, context, template_name)

