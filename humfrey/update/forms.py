from django import forms
from django.forms.models import inlineformset_factory
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse

from .models import UpdateDefinition, UpdatePipeline
from .utils import evaluate_pipeline

class UpdateDefinitionForm(forms.ModelForm):
    cron_schedule = forms.CharField(required=False)

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if self.instance.slug and slug != self.instance.slug:
            raise ValidationError("You cannot change the slug once set")
        if reverse('update:definition-detail', args=[slug]) == reverse('update:definition-create'):
            raise ValidationError("'%s' is a reserved name." % slug)
        return slug

    class Meta:
        model = UpdateDefinition
        fields = ['slug', 'title', 'description', 'cron_schedule']

class UpdatePipelineForm(forms.ModelForm):
    value = forms.CharField(widget=forms.Textarea(attrs={'class': 'pipeline'}))
    def clean_value(self):
        value = self.cleaned_data['value']
        try:
            evaluate_pipeline(value)
        except Exception, e:
            raise ValidationError(e)
        return value

UpdatePipelineFormset = inlineformset_factory(UpdateDefinition,
                                              UpdatePipeline,
                                              UpdatePipelineForm,
                                              can_delete=True,
                                              extra=2)
