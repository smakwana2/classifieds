# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A classified-ads site built with Django 5.2 (SQLite, Pillow for images). Two apps: `ads` (everything about listings, categories, tags, search, images) and `accounts` (signup and account deletion; login/logout come from `django.contrib.auth.urls`). The project package is `classifieds/`. No frontend build step: plain templates in `templates/`, with shared CSS and JS in `static/css/site.css` and `static/js/site.js`. Maps use Leaflet with OpenStreetMap tiles.

## Commands

```bash
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_categories     # starter categories/subcategories (idempotent)
python manage.py runserver

python manage.py test                                    # all tests
python manage.py test ads                                # one app
python manage.py test ads.tests.EditAndImageTests        # one class
python manage.py test ads.tests.AdTestCase.test_search   # one test
python manage.py makemigrations ads
```

There is no linter or formatter configured. Settings come from env vars `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` (default `1`) and `DJANGO_ALLOWED_HOSTS`.

## Architecture

- **Views are function-based.** All listing pages (home, category, tag) go through `_render_ad_list` in `ads/views.py`, which applies `SearchForm` filters (text, category, location/radius), pagination (12 per page) and passes `querystring` so pagination links keep the filters. Add new list-style pages by passing a base queryset to it.
- **Category hierarchy:** `Category.parent` makes subcategories. Filtering by a category always uses `self_and_descendant_ids()` so parent categories include their subcategories' ads. Slugs are generated on save (subcategory slugs include the parent's name). Top-level category emoji come from `CATEGORY_ICONS`, keyed by slug.
- **Geolocation:** ads have optional `latitude`/`longitude` (both or neither, enforced in `AdForm.clean`). Distances and the search radius are in **miles**. Distance search is done in Python with `Ad.distance_miles` (haversine) on purpose, so it works on any database; the result becomes a list, not a queryset.
- **Search by place name:** `SearchForm.near` (e.g. "Oakland, CA", "94110") is geocoded in `SearchForm.clean` via `ads/geocoding.py` (OpenStreetMap Nominatim) and overrides `lat`/`lng`. Nominatim's policy requires the identifying User-Agent, ≤1 request/second and caching, which `geocode()` does; keep it that way. It prefers real places over businesses and treats a bare 5-digit number as a US ZIP. Tests mock `ads.forms.geocode` / `urlopen`, so they never hit the network.
- **Tags and images live on `AdForm`, not the model form fields.** `tag_names` (comma-separated, lowercased, deduped) and `images`/`remove_images` are saved by `AdForm.save_related(ad)`. When creating with `commit=False` (to set `owner`), call `save_related` after saving the ad.
- **Images:** max `AdImage.MAX_PER_AD` (3) per ad, 5 MB each; the limit counts existing minus removed plus added images. Files are deleted by a `post_delete` signal on `AdImage`, so they're cleaned up on cascaded deletes (ad or user deletion) too. Uploads are stored under `media/listings/`, **never under a path containing `/ads/`** — ad blockers hide those images (a test enforces this).
- **Ownership:** edit/delete views only allow the ad's owner and return 404 otherwise. Deleting an account cascades to the user's ads and images.
- **Frontend:** `static/js/site.js` holds shared behavior (map tile layer, photo lightbox via `[data-lightbox]`, upload previews) and loads after Leaflet. OpenStreetMap tiles must send a Referer (`referrerPolicy: 'strict-origin-when-cross-origin'` on the tile layer) because Django's default same-origin Referrer-Policy otherwise causes 403s. Keep the OSM attribution.
- `MEDIA_URL` files are served by Django only through `classifieds/urls.py` in development.
- **Static cache-busting:** `base.html` links `site.css`/`site.js` with `{% versioned_static %}` (`ads/templatetags/assets.py`), which appends `?v=<mtime>`. The dev server sends no Cache-Control, so without it browsers keep showing stale CSS/JS after edits. Use it for any new static asset in templates. Adding a new template tag library needs a dev-server restart (`touch classifieds/settings.py`).

## Tests

Tests are in `ads/tests.py` and `accounts/tests.py`. Image tests use `@override_settings(MEDIA_ROOT=tempfile.mkdtemp())` and the `make_image()` helper (an in-memory PNG); follow that pattern so tests don't write into `media/`. Several tests assert on rendered HTML class names (e.g. `photo-grid photos-3`), so template markup changes may require test updates.
