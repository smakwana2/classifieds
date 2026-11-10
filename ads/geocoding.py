"""Turn a place name ("Oakland, CA", "94110", "Paris") into coordinates.

Uses OpenStreetMap's Nominatim service. Its usage policy asks for an identifying
User-Agent, at most one request per second and caching of results, so lookups
are cached and throttled here. See https://operations.osmfoundation.org/policies/nominatim/
"""
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.core.cache import cache

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'classifieds-django-app/1.0 (+https://github.com/smakwana2/classifieds)'
TIMEOUT = 6  # seconds
CACHE_SECONDS = 60 * 60 * 24 * 7
MISS_CACHE_SECONDS = 60 * 60  # remember "not found" for an hour
US_ZIP = re.compile(r'\d{5}(-\d{4})?')

_lock = threading.Lock()
_last_request = 0.0


class GeocodingUnavailable(Exception):
    """The geocoding service could not be reached or returned an error."""


@dataclass(frozen=True)
class Place:
    latitude: float
    longitude: float
    name: str


PLACE_CATEGORIES = {'place', 'boundary'}  # cities, neighborhoods, ZIP codes, counties...
AREA_KEYS = ('neighbourhood', 'suburb', 'quarter', 'city_district')
CITY_KEYS = ('city', 'town', 'village', 'hamlet', 'municipality', 'county')


def _is_place(result):
    return result.get('category', 'place') in PLACE_CATEGORIES


def _place_name(result, query):
    """A short human name for the area a result is in, never a business name."""
    if _is_place(result):
        # "Oakland, Alameda County, California, United States" -> "Oakland, Alameda County, California"
        return ', '.join(result.get('display_name', query).split(', ')[:3])
    address = result.get('address', {})
    parts = [next((address[k] for k in keys if address.get(k)), None)
             for keys in (AREA_KEYS, CITY_KEYS, ('state', 'country'))]
    return ', '.join(p for p in parts if p) or query


def geocode(query):
    """Return a Place for the query, None if nothing matches; raise GeocodingUnavailable on errors."""
    query = ' '.join(query.split())
    if not query:
        return None
    key = 'geocode:' + hashlib.sha256(query.lower().encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return Place(*cached) if cached else None

    global _last_request
    # Several results so an actual place (city, neighborhood, ZIP) can be preferred over a
    # business with a matching name; addressdetails gives the area name for the fallback.
    params = {'q': query, 'format': 'jsonv2', 'limit': 5, 'addressdetails': 1}
    if US_ZIP.fullmatch(query):
        params['countrycodes'] = 'us'  # a bare 5-digit number is a US ZIP code, not e.g. a Mexican postcode
    params = urllib.parse.urlencode(params)
    request = urllib.request.Request(f'{NOMINATIM_URL}?{params}', headers={'User-Agent': USER_AGENT})
    with _lock:  # at most one request per second from this process
        wait = 1.0 - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                results = json.load(response)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise GeocodingUnavailable(str(exc)) from exc
        finally:
            _last_request = time.monotonic()

    if not results:
        cache.set(key, (), MISS_CACHE_SECONDS)
        return None
    best = next((r for r in results if _is_place(r)), results[0])
    place = Place(float(best['lat']), float(best['lon']), _place_name(best, query))
    cache.set(key, (place.latitude, place.longitude, place.name), CACHE_SECONDS)
    return place
