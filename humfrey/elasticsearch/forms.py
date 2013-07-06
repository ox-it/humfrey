from django import forms

class SearchForm(forms.Form):
    q = forms.CharField(label="Query")
    page = forms.IntegerField(required=False)
    page_size = forms.IntegerField(required=False)
    default_operator = forms.ChoiceField(required=False, choices=(('and', 'and'), ('or', 'or')))
    
    def clean(self):
        cleaned_data = super(SearchForm, self).clean()
        if 'default_operator' not in cleaned_data:
            cleaned_data['default_operator'] = 'and'
        if not cleaned_data.get('page'):
            cleaned_data['page'] = 1
        if not cleaned_data.get('page_size'):
            cleaned_data['page_size'] = 10
        cleaned_data['from'] = (cleaned_data['page'] - 1) * cleaned_data['page_size']
        return cleaned_data
       
