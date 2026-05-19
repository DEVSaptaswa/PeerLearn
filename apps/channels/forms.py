"""apps/channels/forms.py"""
from django import forms
from django.utils.text import slugify
from .models import Channel


class ChannelCreateForm(forms.ModelForm):

    COLOR_CHOICES = [
        ("#5865F2", "Blurple"),
        ("#57F287", "Green"),
        ("#FEE75C", "Yellow"),
        ("#EB459E", "Pink"),
        ("#ED4245", "Red"),
        ("#E67E22", "Orange"),
        ("#9B59B6", "Purple"),
        ("#1ABC9C", "Teal"),
        ("#3776AB", "Python Blue"),
        ("#E67E22", "Amber"),
        ("#2ECC71", "Emerald"),
        ("#E74C3C", "Crimson"),
        ("#3498DB", "Sky Blue"),
        ("#F39C12", "Sunflower"),
        ("#1ABC9C", "Turquoise"),
        ("#E91E63", "Rose"),
    ]

    class Meta:
        model = Channel
        fields = ("name", "description", "icon", "privacy")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.update({"class": "form-control"})

    def clean_name(self):
        return self.cleaned_data["name"].strip().lower().replace(" ", "-")

    def save(self, commit=True):
        channel = super().save(commit=False)
        channel.slug = slugify(channel.name)
        # colour comes from the hidden input, not a model field in the form
        if commit:
            channel.save()
        return channel
