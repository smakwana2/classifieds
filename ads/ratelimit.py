"""Small fixed-window rate limiter on top of Django's cache.

The cache must be shared between server processes for limits to hold across them
(settings use a file-based cache by default; Redis/Memcached work too).
"""
import hashlib
import time

from django.conf import settings
from django.core.cache import cache


def client_ip(request):
    """The client's IP address. Behind a trusted proxy (DJANGO_BEHIND_PROXY=1) the proxy
    appends the real address to X-Forwarded-For, so the last entry is the one to trust."""
    if getattr(settings, 'BEHIND_PROXY', False):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '')


def allow(scope, ident, limit, period):
    """Count one hit for (scope, ident); return False once more than `limit` hits fall
    in the current `period`-second window."""
    window = int(time.time() // period)
    digest = hashlib.sha256(f'{scope}:{ident}'.encode()).hexdigest()[:32]
    key = f'rl:{scope}:{digest}:{window}'
    if cache.add(key, 1, period + 5):
        return limit >= 1
    try:
        count = cache.incr(key)
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, period + 5)
        count = 1
    return count <= limit


def allow_all(scope, ident, rules):
    """Apply several (limit, period) rules, e.g. per minute and per day."""
    return all([allow(f'{scope}:{period}', ident, limit, period) for limit, period in rules])
