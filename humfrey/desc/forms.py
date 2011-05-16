from django import forms

def SparqlQueryForm(*args, **kwargs):
    formats = kwargs.pop('formats')
    formats = sorted([(format, f.name) for (format, f) in formats.iteritems()])

    class _SparqlQueryForm(forms.Form):
        query = forms.CharField(widget=forms.Textarea(), initial="PREFIX owl: <http://www.w3.org/2002/07/owl#>\n\nSELECT DISTINCT ?type WHERE {\n  ?type a owl:Class\n} LIMIT 50")
        format = forms.ChoiceField(choices=formats, initial='html', required=False)
        common_prefixes = forms.BooleanField(label='Assume common namespace prefixes', initial=False, required=False, help_text="When checked, common prefix declarations are prepended to your query.")
    return _SparqlQueryForm(*args, **kwargs)
