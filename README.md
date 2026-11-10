# Classifieds

A simple classified-ads site built with Python and Django.

## Features

- **Post ads** with title, description, price, category, tags and location
- **Browse ads**: latest ads, full-text search, pagination
- **Categories and subcategories**: browsing a category includes its subcategories' ads
- **Tags**: comma-separated tags on each ad, with a page per tag and a popular-tags list
- **Geolocation**: pick a spot on a map (or use your browser's location) when posting; find ads near you or near any place you type (city, neighborhood or ZIP code, looked up with OpenStreetMap) within a radius in miles, sorted by distance; each ad shows a map
- **User accounts**: sign up, log in and log out
- **Delete your account** (password confirmation; deletes all your ads too)
- **Delete your ads** (owners only)

Maps use [Leaflet](https://leafletjs.com/) with OpenStreetMap tiles.

## Screenshots

**Home page: search by place name and radius**, nearest first

![Home page with a search for ads within 25 miles of Oakland, CA](docs/screenshots/home-search.png)

**Ad page** with a photo grid (click to open the lightbox) and a map of the location

![Ad page for a Sony A7 III camera with three photos and a map of the Mission District](docs/screenshots/ad-detail.png)

| Browse by category | Posting an ad: drop a pin on the map |
|---|---|
| ![Categories page with six categories and their subcategories](docs/screenshots/categories.png) | ![Location step of the post-an-ad form with a pin in Palo Alto](docs/screenshots/post-ad-location.png) |

**On a phone**

<img src="docs/screenshots/mobile-search.png" alt="Home page search on a phone" width="300">

Demo listing photos are from Wikimedia Commons under their own licences, and maps are © OpenStreetMap contributors. See [docs/screenshots/CREDITS.md](docs/screenshots/CREDITS.md).

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_categories     # starter categories and subcategories
python manage.py seed_ads            # optional: demo ads around the SF Bay Area, with photos
python manage.py createsuperuser     # optional, for /admin/
python manage.py runserver
```

Then open http://127.0.0.1:8000/.

## Running tests

```bash
python manage.py test
```

## Configuration

Settings are read from environment variables. The defaults are for local development only.

| Variable | Default |
| --- | --- |
| `DJANGO_SECRET_KEY` | an insecure development key |
| `DJANGO_DEBUG` | `1` (set to `0` in production) |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` |
