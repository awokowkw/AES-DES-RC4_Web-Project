import datetime
import re

from django import forms

from .fields import FIELDS

LABELS = {
    'full_name': 'Nama lengkap', 'date_of_birth': 'Tanggal lahir',
    'phone': 'Nomor telepon', 'address': 'Alamat',
}


class ProfileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in FIELDS:
            if name == 'address':
                widget = forms.Textarea(attrs={'rows': 2})
            elif name == 'date_of_birth':
                widget = forms.TextInput(attrs={'type': 'date'})
            else:
                widget = forms.TextInput()
            self.fields[name] = forms.CharField(
                required=False, max_length=2000, label=LABELS[name], widget=widget)

    def clean_date_of_birth(self):
        v = self.cleaned_data['date_of_birth'].strip()
        if not v:
            return ''
        try:
            d = datetime.date.fromisoformat(v)
        except ValueError:
            raise forms.ValidationError('Format tanggal tidak valid.')
        if d > datetime.date.today():
            raise forms.ValidationError('Tanggal lahir tidak boleh di masa depan.')
        return d.isoformat()

    def clean_phone(self):
        v = self.cleaned_data['phone'].strip()
        if v and not re.fullmatch(r'\+?[0-9 \-]{8,20}', v):
            raise forms.ValidationError('Nomor telepon tidak valid.')
        return v


class IdCardForm(forms.Form):
    file = forms.FileField(label='Foto ID card (JPG/PNG, maks 5 MB)')