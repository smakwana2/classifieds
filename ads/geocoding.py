"""Turn a place name ("Oakland, CA", "94110", "Paris") into coordinates.

Uses OpenStreetMap's Nominatim service. Its usage policy asks for an identifying
User-Agent, at most one request per second and caching of results, so lookups
are cached and throttled here. See https://operations.osmfoundation.org/policies/nominatim/

Throttling uses the shared cache, so it holds across server processes: each lookup
reserves its own whole second (cache.add on a per-second key) and nothing is held
while waiting for the network. When the next few seconds are all taken the lookup
fails fast with GeocodingBusy instead of queueing. Each client may also make only a
few uncached lookups per minute and per day (GeocodingRateLimited).
"""
import hashlib
import http.client
import json
import math
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.core.cache import cache

from . import ratelimit

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'classifieds-django-app/1.0 (+https://github.com/smakwana2/classifieds)'
TIMEOUT = 6  # seconds
CACHE_SECONDS = 60 * 60 * 24 * 7
MISS_CACHE_SECONDS = 60 * 60  # remember "not found" for an hour
US_ZIP = re.compile(r'\d{5}(-\d{4})?')
MAX_WAIT_SECONDS = 2  # give up rather than queue when the next slots are taken
CLIENT_LIMITS = [(10, 60), (100, 60 * 60 * 24)]  # uncached lookups per client: per minute, per day

_sleep = time.sleep  # patched in tests


class GeocodingUnavailable(Exception):
    """The geocoding service could not be reached or returned an error."""


class GeocodingBusy(GeocodingUnavailable):
    """Too many lookups are already scheduled for the next few seconds."""


class GeocodingRateLimited(GeocodingUnavailable):
    """This client has made too many new lookups recently."""


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


def _reserve_slot():
    """Claim a whole second, shared across processes, in which this process may call
    Nominatim; return when that second starts. Requests start on second boundaries,
    so two of them are always at least a second apart."""
    first = math.ceil(time.time())
    for second in range(first, first + MAX_WAIT_SECONDS + 1):
        if cache.add(f'geocode:slot:{second}', 1, MAX_WAIT_SECONDS + 10):
            wait = second - time.time()
            if wait > 0:
                _sleep(wait)
            return
    raise GeocodingBusy('all geocoding slots are taken')


def geocode(query, client=None):
    """Return a Place for the query, None if nothing matches.

    Raises GeocodingUnavailable (or its subclasses GeocodingBusy / GeocodingRateLimited)
    when no answer can be given. `client` (e.g. an IP address) is rate-limited for
    lookups that are not already cached.
    """
    query = ' '.join(query.split())
    if not query:
        return None
    key = 'geocode:' + hashlib.sha256(query.lower().encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return Place(*cached) if cached else None
    if client is not None and not ratelimit.allow_all('geocode', client, CLIENT_LIMITS):
        raise GeocodingRateLimited(f'too many new lookups from {client}')

    # Several results so an actual place (city, neighborhood, ZIP) can be preferred over a
    # business with a matching name; addressdetails gives the area name for the fallback.
    params = {'q': query, 'format': 'jsonv2', 'limit': 5, 'addressdetails': 1}
    if US_ZIP.fullmatch(query):
        params['countrycodes'] = 'us'  # a bare 5-digit number is a US ZIP code, not e.g. a Mexican postcode
    params = urllib.parse.urlencode(params)
    request = urllib.request.Request(f'{NOMINATIM_URL}?{params}', headers={'User-Agent': USER_AGENT})
    _reserve_slot()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            results = json.load(response)
    # OSError covers URLError, timeouts and dropped connections; HTTPException covers
    # truncated responses; ValueError covers bad JSON.
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise GeocodingUnavailable(str(exc)) from exc

    if not isinstance(results, list):
        raise GeocodingUnavailable('unexpected response')
    if not results:
        cache.set(key, (), MISS_CACHE_SECONDS)
        return None
    try:
        best = next((r for r in results if _is_place(r)), results[0])
        place = Place(float(best['lat']), float(best['lon']), _place_name(best, query))
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise GeocodingUnavailable('unexpected response') from exc
    cache.set(key, (place.latitude, place.longitude, place.name), CACHE_SECONDS)
    return place
