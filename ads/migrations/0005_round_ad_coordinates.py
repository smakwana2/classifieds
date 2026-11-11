"""Round existing ads' coordinates to 3 decimals (about 100 m), as Ad.save now does."""
from django.db import migrations

COORD_DECIMALS = 3


def round_coordinates(apps, schema_editor):
    Ad = apps.get_model('ads', 'Ad')
    for ad in Ad.objects.exclude(latitude=None).exclude(longitude=None).only('latitude', 'longitude'):
        ad.latitude = round(ad.latitude, COORD_DECIMALS)
        ad.longitude = round(ad.longitude, COORD_DECIMALS)
        ad.save(update_fields=['latitude', 'longitude'])


class Migration(migrations.Migration):
    dependencies = [('ads', '0004_adimage_thumbnail')]
    operations = [migrations.RunPython(round_coordinates, migrations.RunPython.noop)]
