"""Re-encode stored ad photos that predate upload processing.

Strips metadata (including GPS) from older uploads, renames them randomly and adds
thumbnails. Photos that already have a thumbnail were processed on upload and are skipped.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from ads.images import process
from ads.models import AdImage


class Command(BaseCommand):
    help = 'Strip metadata from, and add thumbnails to, photos uploaded before processing existed.'

    def handle(self, *args, **options):
        done = missing = 0
        for image in AdImage.objects.filter(thumbnail=''):
            storage, old_name = image.image.storage, image.image.name
            if not storage.exists(old_name):
                missing += 1
                self.stderr.write(f'Missing file, skipped: {old_name}')
                continue
            with storage.open(old_name, 'rb') as fh:
                photo, thumb = process(fh)
            with transaction.atomic():
                image.image.save(photo.name, photo, save=False)
                image.thumbnail.save(thumb.name, thumb, save=False)
                image.save(update_fields=['image', 'thumbnail'])
                transaction.on_commit(lambda s=storage, n=old_name: s.delete(n))
            done += 1
        self.stdout.write(self.style.SUCCESS(f'Processed {done} photo(s), {missing} missing.'))
