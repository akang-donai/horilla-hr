from django import forms as django_forms
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from base.forms import ModelForm

from .models import GeoFencing


class GeoFencingSetupForm(ModelForm):
    verbose_name = _("Geofence Configuration")

    class Meta:
        model = GeoFencing
        exclude = ["company_id"]
        widgets = {
            "exempt_departments": django_forms.SelectMultiple(
                attrs={"class": "form-control", "multiple": True}
            ),
        }
