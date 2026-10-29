from django import forms
from django.utils.text import slugify

from .models import Ad, Category, Tag


class AdForm(forms.ModelForm):
    tag_names = forms.CharField(
        label='Tags',
        required=False,
        help_text='Comma-separated, e.g. "vintage, bargain".',
    )

    class Meta:
        model = Ad
        fields = ['title', 'description', 'price', 'category', 'location_name', 'latitude', 'longitude']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
            'latitude': forms.NumberInput(attrs={'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'step': 'any'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.select_related('parent').order_by(
            'parent__name', 'name'
        )
        if self.instance.pk:
            self.fields['tag_names'].initial = ', '.join(t.name for t in self.instance.tags.all())

    def clean(self):
        cleaned = super().clean()
        lat, lng = cleaned.get('latitude'), cleaned.get('longitude')
        if (lat is None) != (lng is None):
            raise forms.ValidationError('Enter both latitude and longitude, or neither.')
        return cleaned

    def clean_tag_names(self):
        names = []
        for raw in self.cleaned_data['tag_names'].split(','):
            name = raw.strip().lower()
            if name and slugify(name) and name not in names:
                names.append(name[:50])
        return names

    def save(self, commit=True):
        ad = super().save(commit=commit)
        if commit:
            self.save_tags(ad)
        return ad

    def save_tags(self, ad):
        tags = []
        for name in self.cleaned_data['tag_names']:
            tag = Tag.objects.filter(slug=slugify(name)).first() or Tag.objects.create(name=name)
            tags.append(tag)
        ad.tags.set(tags)


class SearchForm(forms.Form):
    q = forms.CharField(label='Search', required=False)
    category = forms.ModelChoiceField(
        queryset=Category.objects.select_related('parent').order_by('parent__name', 'name'),
        required=False,
        empty_label='All categories',
    )
    lat = forms.FloatField(required=False, min_value=-90, max_value=90, widget=forms.HiddenInput)
    lng = forms.FloatField(required=False, min_value=-180, max_value=180, widget=forms.HiddenInput)
    radius = forms.FloatField(label='Within (km)', required=False, min_value=1, max_value=20000)
