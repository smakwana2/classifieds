"""Light/dark theme choice, saved in the `theme` cookie.

The server renders <html data-theme="..."> from the cookie, so the chosen theme is
there from the first paint (no flash, no inline script). Without a choice the site
follows the system setting (prefers-color-scheme). static/js/site.js switches
instantly without a reload; the form below is the no-JavaScript fallback.
"""
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

THEMES = ('light', 'dark')
COOKIE = 'theme'
COOKIE_MAX_AGE = 60 * 60 * 24 * 365
THEME_COLORS = {'light': '#0f5c4d', 'dark': '#111513'}  # browser UI colour (<meta name="theme-color">)


def chosen_theme(request):
    value = request.COOKIES.get(COOKIE, '')
    return value if value in THEMES else ''


def theme_context(request):
    theme = chosen_theme(request)
    return {'theme': theme, 'theme_color': THEME_COLORS.get(theme, THEME_COLORS['light'])}


@require_POST
def set_theme(request):
    theme = request.POST.get('theme', '')
    target = request.POST.get('next', '/')
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        target = '/'
    response = redirect(target)
    if theme in THEMES:
        response.set_cookie(COOKIE, theme, max_age=COOKIE_MAX_AGE, samesite='Lax', secure=request.is_secure())
    return response
