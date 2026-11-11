import math

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify

# Coordinates are stored and shown rounded to 3 decimals (about 100 m), so an ad's
# public map pin never reveals a seller's exact address.
COORD_DECIMALS = 3
EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1, lng1, lat2, lng2):
    """Great-circle distance in miles between two points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat, lng, miles):
    """Queryset filters for a box that contains every point within `miles` of (lat, lng).

    Lets the database discard far-away ads before exact distances are computed. Near the
    poles or across the 180° meridian only latitude is limited, which is still correct.
    """
    dlat = miles / 69.0
    box = {'latitude__gte': lat - dlat, 'latitude__lte': lat + dlat}
    cos_lat = math.cos(math.radians(lat))
    if cos_lat > 0.01:
        dlng = miles / (69.172 * cos_lat)
        if -180 <= lng - dlng and lng + dlng <= 180:
            box.update(longitude__gte=lng - dlng, longitude__lte=lng + dlng)
    return box

def unique_slug(model, base, pk=None, max_length=50):
    """`base`, or `base-2`, `base-3`... whichever is not taken by another row."""
    base = base[:max_length - 4] or 'item'
    slug, n = base, 2
    while model.objects.filter(slug=slug).exclude(pk=pk).exists():
        slug, n = f'{base}-{n}', n + 1
    return slug


CATEGORY_ICONS = {
    'for-sale': '🛍️',
    'vehicles': '🚗',
    'housing': '🏠',
    'jobs': '💼',
    'services': '🛠️',
    'community': '🤝',
}


class Category(models.Model):
    """A category; categories with a parent are subcategories."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='subcategories',
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['parent', 'name'], name='unique_category_name_per_parent'),
        ]

    def __str__(self):
        return f'{self.parent.name} › {self.name}' if self.parent else self.name

    def clean(self):
        # Exactly two levels (category › subcategory), which also rules out loops.
        if self.parent_id is None:
            return
        if self.parent_id == self.pk:
            raise ValidationError({'parent': 'A category cannot be its own parent.'})
        if self.parent.parent_id is not None:
            raise ValidationError({'parent': 'Choose a top-level category; subcategories cannot have subcategories.'})
        if self.pk and self.subcategories.exists():
            raise ValidationError({'parent': 'This category has subcategories, so it cannot become one itself.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f'{self.parent.name} {self.name}' if self.parent else self.name)
            self.slug = unique_slug(Category, base, self.pk, max_length=120)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('ads:category', args=[self.slug])

    @property
    def icon(self):
        """Emoji for the top-level category this one belongs to."""
        root = self.parent if self.parent_id else self
        return CATEGORY_ICONS.get(root.slug, '🏷️')

    def self_and_descendant_ids(self):
        return [self.pk, *self.subcategories.values_list('pk', flat=True)]


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            # "c++", "c#" and "c" all slugify to "c", so later ones get "c-2", "c-3"...
            self.slug = unique_slug(Tag, slugify(self.name), self.pk, max_length=60)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('ads:tag', args=[self.slug])


class Ad(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='ads', on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    description = models.TextField(max_length=5000)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                validators=[MinValueValidator(0)])
    category = models.ForeignKey(Category, related_name='ads', on_delete=models.PROTECT)
    tags = models.ManyToManyField(Tag, related_name='ads', blank=True)
    location_name = models.CharField('location', max_length=150, blank=True)
    latitude = models.FloatField(
        null=True, blank=True, db_index=True, validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.FloatField(
        null=True, blank=True, db_index=True, validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.latitude is not None:
            self.latitude = round(self.latitude, COORD_DECIMALS)
        if self.longitude is not None:
            self.longitude = round(self.longitude, COORD_DECIMALS)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('ads:detail', args=[self.pk])

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

    def distance_miles(self, lat, lng):
        """Great-circle (haversine) distance in miles from this ad to (lat, lng), or None."""
        if not self.has_coordinates:
            return None
        return haversine_miles(self.latitude, self.longitude, lat, lng)


class AdImage(models.Model):
    MAX_PER_AD = 3

    ad = models.ForeignKey(Ad, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='listings/%Y/%m/')
    thumbnail = models.ImageField(upload_to='listings/%Y/%m/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']

    def __str__(self):
        return self.image.name

    @classmethod
    def create_from_file(cls, ad, fileobj):
        """Store a photo for an ad, re-encoded without metadata and with a thumbnail."""
        from .images import process
        photo, thumb = process(fileobj)
        return cls.objects.create(ad=ad, image=photo, thumbnail=thumb)

    @property
    def thumb_url(self):
        return (self.thumbnail or self.image).url


@receiver(post_delete, sender=AdImage)
def delete_image_files(sender, instance, **kwargs):
    # Runs for cascaded deletes too (deleting an ad or a user), unlike Model.delete().
    # Files go only once the transaction commits, so a rolled-back delete keeps its photos.
    files = [(f.storage, f.name) for f in (instance.image, instance.thumbnail) if f]
    transaction.on_commit(lambda: [storage.delete(name) for storage, name in files])
