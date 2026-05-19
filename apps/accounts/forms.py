"""apps/accounts/forms.py"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Profile


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    display_name = forms.CharField(max_length=60, required=False)

    class Meta:
        model = User
        fields = ("username", "email", "display_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": "form-control", "autofocus": True}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )


class ProfileEditForm(forms.ModelForm):
    display_name = forms.CharField(max_length=60, required=False)
    bio = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    class Meta:
        model = Profile
        fields = ("avatar",)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["display_name"].initial = self.user.display_name
            self.fields["bio"].initial = self.user.bio
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.display_name = self.cleaned_data.get("display_name", "")
            self.user.bio = self.cleaned_data.get("bio", "")
            self.user.save(update_fields=["display_name", "bio"])
        if commit:
            profile.save()
        return profile
