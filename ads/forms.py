from django import forms
from django.utils.text import slugify

from .models import Ad, AdImage, Category, Tag

MAX_IMAGE_BYTES = 5 * 1024 * 1024


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data] if data else []
        if not files and self.required:
            raise forms.ValidationError(self.error_messages['required'], code='required')
        return [super(MultipleImageField, self).clean(f, initial) for f in files]


class AdForm(forms.ModelForm):
    tag_names = forms.CharField(
        label='Tags',
        required=False,
        help_text='Comma-separated, e.g. "vintage, bargain".',
    )
    images = MultipleImageField(
        required=False,
        help_text=f'Up to {AdImage.MAX_PER_AD} images in total, 5 MB each.',
        widget=MultipleFileInput(attrs={'accept': 'image/*'}),
    )
    remove_images = forms.ModelMultipleChoiceField(
        queryset=AdImage.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
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
            self.fields['remove_images'].queryset = self.instance.images.all()
        else:
            del self.fields['remove_images']

    def clean(self):
        cleaned = super().clean()
        lat, lng = cleaned.get('latitude'), cleaned.get('longitude')
        if (lat is None) != (lng is None):
            raise forms.ValidationError('Enter both latitude and longitude, or neither.')

        existing = self.instance.images.count() if self.instance.pk else 0
        removed = len(cleaned.get('remove_images') or [])
        added = len(cleaned.get('images') or [])
        if existing - removed + added > AdImage.MAX_PER_AD:
            self.add_error(
                'images',
                f'An ad can have at most {AdImage.MAX_PER_AD} images '
                f'({existing - removed} kept, {added} added).',
            )
        return cleaned

    def clean_images(self):
        images = self.cleaned_data['images']
        for image in images:
            if image.size > MAX_IMAGE_BYTES:
                raise forms.ValidationError(f'“{image.name}” is larger than 5 MB.')
        return images

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
            self.save_related(ad)
        return ad

    def save_related(self, ad):
        """Save tags and images; call after the ad itself has been saved."""
        tags = []
        for name in self.cleaned_data['tag_names']:
            tag = Tag.objects.filter(slug=slugify(name)).first() or Tag.objects.create(name=name)
            tags.append(tag)
        ad.tags.set(tags)

        for image in self.cleaned_data.get('remove_images') or []:
            image.delete()
        for upload in self.cleaned_data['images']:
            AdImage.objects.create(ad=ad, image=upload)


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
