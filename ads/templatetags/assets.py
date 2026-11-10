"""{% versioned_static %}: a static URL that changes whenever the file changes.

The dev server sends no Cache-Control header for static files, so browsers cache
site.css/site.js heuristically and keep showing old versions after an edit.
Appending ?v=<last-modified time> gives each version its own URL.
"""
import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def versioned_static(path):
    url = static(path)
    found = finders.find(path)
    if not found:
        return url
    version = int(os.path.getmtime(found))
    return f"{url}{'&' if '?' in url else '?'}v={version}"
