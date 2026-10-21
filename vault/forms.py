"""Tahap 2: Django forms for the existing account registration and login flow."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model


User = get_user_model()


class SYNKUserCreationForm(UserCreationForm):
    full_name = forms.CharField(
        label="Full name",
        max_length=150,
        strip=True,
    )
    email = forms.EmailField(label="Email")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data["full_name"].strip()
        first_name, separator, last_name = full_name.partition(" ")
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
