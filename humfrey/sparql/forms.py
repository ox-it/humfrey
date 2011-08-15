from django import forms
from django.conf import settings

def SparqlQueryForm(*args, **kwargs):
    formats = kwargs.pop('formats')

    class _SparqlQueryForm(forms.Form):
        query = forms.CharField(widget=forms.Textarea(), initial="SELECT DISTINCT ?type WHERE {\n  ?type a owl:Class\n} LIMIT 50")
        format = forms.ChoiceField(label='Results format',
                                   choices=formats, initial='html', required=False)
        common_prefixes = forms.BooleanField(label='Assume common namespace prefixes',
                                             required=False, help_text="When checked, common prefix declarations are prepended to your query.", initial=getattr(settings, 'SPARQL_FORM_COMMON_PREFIXES', True))
    return _SparqlQueryForm(*args, **kwargs)
