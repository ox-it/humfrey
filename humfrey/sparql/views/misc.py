import functools

from django_conneg.decorators import renderer

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

        context['results'] = self.endpoint.query(query, defer=True)
        self.update_context_for_deferral()
        context.update(self.get_additional_context(request, *args, **kwargs))
        context = self.finalize_context(request, context, *args, **kwargs)

        return self.render()

