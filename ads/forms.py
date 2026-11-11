from django import forms
from django.utils.text import slugify

from .geocoding import GeocodingBusy, GeocodingRateLimited, GeocodingUnavailable, geocode
from .images import MAX_BYTES as MAX_IMAGE_BYTES, validate_upload
from .models import Ad, AdImage, Category, Tag


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data] if data else []
        if not files and self.required:
            raise forms.ValidationError(self.error_messages['required'], code='required')
        # Cheap checks first, so oversized or too many files are never parsed as images.
        if len(files) > AdImage.MAX_PER_AD:
            raise forms.ValidationError(f'An ad can have at most {AdImage.MAX_PER_AD} images.')
        for f in files:
            if f.size > MAX_IMAGE_BYTES:
                raise forms.ValidationError(f'“{f.name}” is larger than 5 MB.')
        cleaned = [super(MultipleImageField, self).clean(f, initial) for f in files]
        for f in cleaned:
            validate_upload(f)
        return cleaned


class AdForm(forms.ModelForm):
    tag_names = forms.CharField(
        label='Tags',
        required=False,
        help_text='Comma-separated, e.g. "vintage, bargain".',
    )
    images = MultipleImageField(
        required=False,
        help_text=f'Up to {AdImage.MAX_PER_AD} images in total, 5 MB each.',
        widget=MultipleFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
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
            AdImage.create_from_file(ad, upload)


MAX_RADIUS_MILES = 500  # also the search area when a location is given without a radius


class SearchForm(forms.Form):
    q = forms.CharField(label='Search', required=False)
    category = forms.ModelChoiceField(
        queryset=Category.objects.select_related('parent').order_by('parent__name', 'name'),
        required=False,
        empty_label='All categories',
    )
    near = forms.CharField(label='Location', required=False, max_length=200)
    lat = forms.FloatField(required=False, min_value=-90, max_value=90, widget=forms.HiddenInput)
    lng = forms.FloatField(required=False, min_value=-180, max_value=180, widget=forms.HiddenInput)
    radius = forms.FloatField(label='Within (miles)', required=False, min_value=1, max_value=MAX_RADIUS_MILES)

    def __init__(self, *args, client=None, **kwargs):
        self.client = client  # who is searching (IP address), for geocoding rate limits
        super().__init__(*args, **kwargs)

    def clean(self):
        """A typed location wins over lat/lng; it is geocoded into lat/lng and a display name."""
        cleaned = super().clean()
        near = cleaned.get('near', '').strip()
        cleaned['place_name'] = None
        if near:
            try:
                place = geocode(near, client=self.client)
            except GeocodingRateLimited:
                self.add_error('near', 'You\u2019ve searched for a lot of new places. Please wait a minute and try again.')
                return cleaned
            except GeocodingBusy:
                self.add_error('near', 'Location search is busy right now. Please try again in a few seconds.')
                return cleaned
            except GeocodingUnavailable:
                self.add_error('near', 'Location search is unavailable right now. Please try again shortly.')
                return cleaned
            if place is None:
                self.add_error('near', f'Couldn\u2019t find \u201c{near}\u201d. Try a city, neighborhood or ZIP code.')
                return cleaned
            cleaned['lat'], cleaned['lng'], cleaned['place_name'] = place.latitude, place.longitude, place.name
        return cleaned
