import abc
import urllib.request, urllib.parse, urllib.error
import urllib.parse

from django import forms
from django.urls import reverse
from django.shortcuts import render
from django.template import RequestContext, TemplateDoesNotExist
from django.template.loader import get_template
from django.utils.decorators import classonlymethod
from django_conneg.decorators import renderer
from django_conneg.http import HttpResponseSeeOther
from django_conneg.views import HTMLView

from humfrey.linkeddata.views import MappingView
from humfrey.results.views.standard import RDFView
from humfrey.results.views.json import JSONRDFView
from humfrey.sparql.views import StoreView

class FeedForm(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs.pop('endpoint')

        conneg = kwargs.pop('conneg')
        format_choices = [(renderer.format, renderer.name) for renderer in conneg.renderers]
        format_choices.insert(0, ('', '-'*20))
        self.base_fields['format'].choices = format_choices

        orderings = kwargs.pop('orderings')
        order_by_choices = [(k, v[0]) for k,v in orderings.items()]
        order_by_choices.insert(0, ('', '-'*20))
        self.base_fields['order_by'].choices = order_by_choices

        super(FeedForm, self).__init__(*args, **kwargs)

    format = forms.ChoiceField(required=False)
    order_by = forms.ChoiceField(required=False)
    css = forms.CharField(label="Additional CSS URL",
                          help_text="Used for HTML-based formats; a link tag will be added.",
                          required=False)

class FeedView(StoreView, MappingView, JSONRDFView, RDFView, HTMLView, metaclass=abc.ABCMeta):
    template_name = 'feeds/view'
    snippet_template = 'feeds/snippet'
    item_template = 'feeds/item'

    slug = None
    meta = None

    @abc.abstractproperty
    def form_class(self): pass

    @abc.abstractproperty
    def name(self): pass

    @abc.abstractproperty
    def plural_name(self): pass

    @abc.abstractproperty
    def description(self): pass

    @classonlymethod
    def as_view(self, **initkwargs):
        view = super(FeedView, self).as_view(**initkwargs)
        for n in ('orderings', 'form_class', 'name', 'description', 'plural_name'):
            setattr(view, n, getattr(self, n))
        view.meta, view.slug = initkwargs['meta'], initkwargs['slug']
        return view

    def get(self, request):
        self.form = self.form_class(request.GET,
                                    conneg=self.conneg,
                                    endpoint=self.endpoint,
                                    orderings=self.orderings)

        qs = request.META['QUERY_STRING']
        qs = urllib.parse.parse_qs(qs, keep_blank_values=1)
        qs.pop('format', None)
        qs = urllib.parse.urlencode(qs, True)
        config_url = reverse('feeds:feed-config', args=[self.slug]) + '?' + qs

        self.context.update({'feed': self.meta,
                             'config_url': config_url,
                             'templates': {'snippet': self._template_name_joiner(self.snippet_template),
                                           'item': self._template_name_joiner(self.item_template),
                                           }})

        if self.form.is_valid():
            query_context = self.form.cleaned_data.copy()
            query_context.update({'url': request.build_absolute_uri()})
            results = self.endpoint.query(self.get_query(query_context), defer=True)
            self.context.update({'results': results,
                                 'cleaned_data': self.form.cleaned_data})
            return self.render()
        else:
            return HttpResponseSeeOther(self.context['config_url'])

    def get_query(self, query_context):
        t = get_template(self.query_template)
        c = RequestContext(self.request, query_context)
        return t.render(c)

    def sort_subjects(self, subjects):
        order_by = self.form.cleaned_data.get('order_by')
        if order_by:
            subjects.sort(key=self.orderings[order_by][1])
        else:
            super(FeedView, self).sort_subjects(subjects)

    def _template_name_joiner(self, template_name):
        class Joiner(object):
            def __init__(self, join_template_name, template_name):
                self.join_template_name = join_template_name
                self.template_name = template_name
            def __getattr__(self2, name):
                return self.join_template_name(template_name, name)
        return Joiner(self.join_template_name, template_name)

    @renderer(format='iframe', mimetypes=(), name='IFrame')
    def render_iframe(self, request, context, template_name):
        self.undefer()
        template_name = self.join_template_name(template_name, 'iframe')
        if template_name is None:
            return NotImplemented
        try:
            return render(request, template_name, context, content_type='text/html')
        except TemplateDoesNotExist:
            raise
            return NotImplemented
