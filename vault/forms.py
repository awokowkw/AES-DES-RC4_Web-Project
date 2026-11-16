"""Form profil/ID card (backend) dan form akun SYNK (frontend)."""
import datetime
import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .fields import FIELDS

User = get_user_model()

LABELS = {
    'full_name': 'Nama lengkap', 'date_of_birth': 'Tanggal lahir',
    'phone': 'Nomor telepon', 'address': 'Alamat',
}


# ------------------------------------------------------------ profil (BE)
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


# ------------------------------------------------------------ akun (FE)
class SYNKUserCreationForm(UserCreationForm):
    full_name = forms.CharField(label="Full name", max_length=150, strip=True)
    email = forms.EmailField(label="Email")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        first_name, separator, last_name = self.cleaned_data["full_name"].strip().partition(" ")
        user.first_name = first_name
        user.last_name = last_name if separator else ""
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class SYNKAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )

    def clean(self):
        identifier = self.cleaned_data.get("username", "").strip()
        if "@" in identifier:
            account = User.objects.filter(email__iexact=identifier).first()
            if account:
                self.cleaned_data["username"] = account.get_username()
        return super().clean()