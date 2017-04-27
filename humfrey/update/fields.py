from django.db import models
from django import forms


class PasswordField(forms.CharField):
    widget = forms.Textarea


class HiddenCharField(models.CharField):
    def formfield(self, **kwargs):
        defaults = {'form_class': PasswordField}
        defaults.update(kwargs)
        return super(HiddenCharField, self).formfield(**defaults)