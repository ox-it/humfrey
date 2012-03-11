from django import forms

class SearchForm(forms.Form):
    q = forms.CharField(label="Query")
    page = forms.IntegerField(required=False)
    page_size = forms.IntegerField(required=False)
