"""Checking and re-encoding uploaded photos.

Every photo is re-saved by the server before it is stored, which:
- strips EXIF/XMP/ICC metadata (phone photos carry GPS coordinates of where they were taken),
- applies the EXIF orientation first, so photos still display the right way up,
- caps the size (MAX_SIDE) and makes a small thumbnail for listing pages,
- gives the files random names, so the uploader's own filename is never published.
Only JPEG, PNG and WebP are accepted, judged by the file's content, not its name.
"""
import io
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}
MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000  # e.g. 8000 x 5000; larger images are rejected before decoding
MAX_SIDE = 2000  # longest side of the stored photo
THUMB_SIDE = 640  # longest side of the listing thumbnail
QUALITY = 85

# Pillow refuses (DecompressionBombError) anything over 2x this before decoding it.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def validate_upload(upload):
    """Reject files that are too big or not a JPEG/PNG/WebP photo of a sane size.

    Call after Django's ImageField has parsed the file (it sets ``upload.image``).
    """
    image = getattr(upload, 'image', None)
    if image is None or image.format not in ALLOWED_FORMATS:
        raise ValidationError(f'“{upload.name}” is not a JPG, PNG or WebP photo.')
    width, height = image.size
    if width * height > MAX_PIXELS:
        raise ValidationError(f'“{upload.name}” is too large ({width} × {height} pixels).')


def _encode(image, side):
    image = image.copy()
    image.thumbnail((side, side), Image.LANCZOS)
    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGBA')
        background = Image.new('RGB', image.size, 'white')
        background.paste(image, mask=image.getchannel('A'))
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    buffer = io.BytesIO()
    # No exif=/icc_profile= arguments, so no metadata is written.
    image.save(buffer, 'JPEG', quality=QUALITY, optimize=True, progressive=True)
    return buffer.getvalue()


def process(fileobj):
    """Return (photo, thumbnail) as ContentFiles with random names and no metadata."""
    fileobj.seek(0)
    with Image.open(fileobj) as source:
        if source.format not in ALLOWED_FORMATS:
            raise ValidationError('Only JPG, PNG and WebP photos are accepted.')
        image = ImageOps.exif_transpose(source)
        image.load()
    name = uuid.uuid4().hex
    return (ContentFile(_encode(image, MAX_SIDE), name=f'{name}.jpg'),
            ContentFile(_encode(image, THUMB_SIDE), name=f'{name}-thumb.jpg'))
