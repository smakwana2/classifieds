"""{% versioned_static %}: a static URL that changes whenever the file changes.

In production, static files are stored with content hashes in their names
(ManifestStaticFilesStorage, set up when DEBUG is off), so the URL already changes
with the content and this is plain {% static %}.

In development the dev server sends no Cache-Control header for static files, so
browsers cache site.css/site.js heuristically and keep showing old versions after
an edit. There, ?v=<last-modified time> gives each version its own URL.
"""
import os

from django import template
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import ManifestFilesMixin, staticfiles_storage
from django.templatetags.static import static

register = template.Library()


def uses_hashed_names():
    return isinstance(staticfiles_storage, ManifestFilesMixin)


@register.simple_tag
def versioned_static(path):
    url = static(path)
    if uses_hashed_names():
        return url
    found = finders.find(path)
    if not found:
        return url
    version = int(os.path.getmtime(found))
    return f"{url}{'&' if '?' in url else '?'}v={version}"
