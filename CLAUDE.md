# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A classified-ads site built with Django 5.2 (SQLite, Pillow for images). Two apps: `ads` (everything about listings, categories, tags, search, images) and `accounts` (signup and account deletion; login/logout come from `django.contrib.auth.urls`). The project package is `classifieds/`. No frontend build step: plain templates in `templates/`, with shared CSS and JS in `static/css/site.css` and `static/js/site.js`. Maps use Leaflet with OpenStreetMap tiles.

## Commands

```bash
source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=1                # local development; settings refuse to start otherwise
python manage.py migrate
python manage.py seed_categories     # starter categories/subcategories (idempotent)
python manage.py seed_ads            # demo Bay Area ads with real photos (idempotent; --fresh recreates)
python manage.py runserver

python manage.py test                                    # all tests
python manage.py test ads                                # one app
python manage.py test ads.tests.EditAndImageTests        # one class
python manage.py test ads.tests.AdTestCase.test_search   # one test
python manage.py makemigrations ads
```

There is no linter or formatter configured. Settings come from env vars (see README "Deploying"). They **fail safe**: `DJANGO_DEBUG` defaults to `0`, and without DEBUG a `DJANGO_SECRET_KEY` is required, so run `export DJANGO_DEBUG=1` before using `manage.py` locally (the Makefile does this for you; `manage.py test` works either way). With DEBUG off, HTTPS redirect, HSTS and secure cookies are on.

## Architecture

- **Views are function-based.** All listing pages (home, category, tag) go through `_render_ad_list` in `ads/views.py`, which applies `SearchForm` filters (text, category, location/radius), pagination (12 per page) and passes `querystring` so pagination links keep the filters. Add new list-style pages by passing a base queryset to it.
- **Category hierarchy:** `Category.parent` makes subcategories, **exactly two levels** (`Category.clean` rejects deeper nesting and loops; the admin runs it). Filtering by a category always uses `self_and_descendant_ids()` so parent categories include their subcategories' ads. Category and tag slugs are generated on save and made unique with `-2`, `-3`... (`unique_slug`; subcategory slugs include the parent's name). Tags are looked up by **name**, never by slug ("c++" and "c#" share a slugified form). Top-level category emoji come from `CATEGORY_ICONS`, keyed by slug.
- **Geolocation:** ads have optional `latitude`/`longitude` (both or neither, enforced in `AdForm.clean`). Distances and the search radius are in **miles**, capped at `MAX_RADIUS_MILES` (500, also the area searched when no radius is given). Distance search (`_nearest_page` in `ads/views.py`) narrows candidates with an indexed `bounding_box()` in SQL, computes exact `haversine_miles` in Python on `(id, lat, lng)` rows only (works on any database), and loads full ads just for the current page. Text and category filters still apply when the location field is invalid.
- **Search by place name:** `SearchForm.near` (e.g. "Oakland, CA", "94110") is geocoded in `SearchForm.clean` via `ads/geocoding.py` (OpenStreetMap Nominatim) and overrides `lat`/`lng`. Nominatim's policy requires the identifying User-Agent, ≤1 request/second and caching, which `geocode()` does; keep it that way. The throttle and the cache use the **shared Django cache** (file cache by default, Redis via `DJANGO_REDIS_URL`; LocMem in tests), so they hold across server processes: each lookup reserves a whole second with `cache.add`, nothing is locked while waiting on the network, and it fails fast with `GeocodingBusy` when the next seconds are taken. Uncached lookups are rate-limited per client IP (`ads/ratelimit.py`, `GeocodingRateLimited`). All network/format errors become `GeocodingUnavailable`. It prefers real places over businesses and treats a bare 5-digit number as a US ZIP. Tests mock `ads.forms.geocode` / `urlopen`, so they never hit the network.
- **Tags and images live on `AdForm`, not the model form fields.** `tag_names` (comma-separated, lowercased, deduped) and `images`/`remove_images` are saved by `AdForm.save_related(ad)`. When creating with `commit=False` (to set `owner`), call `save_related` after saving the ad.
- **Images:** max `AdImage.MAX_PER_AD` (3) per ad, 5 MB each; the limit counts existing minus removed plus added images. Only JPEG/PNG/WebP (judged by content) up to `ads.images.MAX_PIXELS`. **Always store photos via `AdImage.create_from_file()`**, which re-encodes them (`ads/images.py`): strips EXIF/GPS and other metadata, applies orientation, caps size, gives a random filename and makes a thumbnail (`thumb_url`, used on listing pages). `python manage.py reprocess_images` does the same for older uploads. Files are deleted by a `post_delete` signal on `AdImage` via `transaction.on_commit`, so they're cleaned up on cascaded deletes but survive rollbacks (tests use `captureOnCommitCallbacks(execute=True)`). Uploads are stored under `media/listings/`, **never under a path containing `/ads/`** — ad blockers hide those images (a test enforces this).
- **Location privacy:** `Ad.save()` rounds coordinates to `COORD_DECIMALS` (3, about 100 m), so map pins never reveal an exact address.
- **Ownership:** edit/delete views only allow the ad's owner and return 404 otherwise. Create/edit views are `transaction.atomic`, so a failure while saving tags or photos leaves no half-saved ad. Deleting an account cascades to the user's ads and images.
- **Frontend:** `static/js/site.js` holds **all** page behavior (map tile layer, ad and form maps, search-bar location, photo lightbox via `[data-lightbox]`, upload previews), each block guarded by the elements it needs, and loads after Leaflet. Leaflet and the fonts are **self-hosted** in `static/vendor/` (Leaflet verified against npm's integrity hash; fonts under OFL).
- **Content Security Policy** (`classifieds/middleware.py`): scripts, styles, fonts and images from the site itself only, plus OpenStreetMap tiles. So **no inline `<script>`, `style=""` attributes, `on*=` handlers or third-party URLs in templates** (a test enforces this); use classes in `site.css` and code in `site.js`. The admin gets inline styles. OpenStreetMap tiles must send a Referer (`referrerPolicy: 'strict-origin-when-cross-origin'` on the tile layer) because Django's default same-origin Referrer-Policy otherwise causes 403s. Keep the OSM attribution.
- **Demo data:** `seed_ads` creates ads owned by `bayarea_demo` (unusable password; delete the user to remove them) from `DEMO_ADS`, using photos bundled in `ads/seed_data/photos/`. Demo photos must be real, freely licensed photos of the item, never generated placeholders, and each must be credited in `ads/seed_data/CREDITS.md` (a test enforces this).
- **Abuse limits** (`ads/ratelimit.py`, cache-based fixed windows; `client_ip()` trusts `X-Forwarded-For` only with `DJANGO_BEHIND_PROXY=1`): login failures per IP and per username and delete-account password failures are throttled (`accounts/views.py`, `ThrottledLoginView` replaces Django's login URL); signups per IP per hour; ads per user per day and in total (`ads/views.py`); max 10 tags, 5,000-character descriptions, `DATA_UPLOAD_MAX_NUMBER_FILES = 3`. Signup usernames are ASCII-only and unique ignoring case. There are deliberately **no password-reset routes** (emails are optional and unverified). Tests that touch limits call `cache.clear()` in `setUp`.
- `MEDIA_URL` files are served by Django only through `classifieds/urls.py` in development.
- **Static cache-busting:** `base.html` links `site.css`/`site.js` with `{% versioned_static %}` (`ads/templatetags/assets.py`), which appends `?v=<mtime>`. The dev server sends no Cache-Control, so without it browsers keep showing stale CSS/JS after edits. Use it for any new static asset in templates. Adding a new template tag library needs a dev-server restart (`touch classifieds/settings.py`).

## Tests

Tests are in `ads/tests.py` and `accounts/tests.py`. Image tests use `@override_settings(MEDIA_ROOT=tempfile.mkdtemp())` and the `make_image()` helper (an in-memory PNG); follow that pattern so tests don't write into `media/`. Several tests assert on rendered HTML class names (e.g. `photo-grid photos-3`), so template markup changes may require test updates.
