from django.conf import settings
from django.shortcuts import render

from classifieds.theme import COOKIE_MAX_AGE as THEME_COOKIE_MAX_AGE

from . import policy


def _context():
    return {
        'operator': settings.SITE_OPERATOR,
        'contact_email': settings.SITE_CONTACT_EMAIL,
        'dmca_agent': settings.DMCA_AGENT,
        'privacy_effective': policy.PRIVACY_EFFECTIVE,
        'terms_effective': policy.TERMS_EFFECTIVE,
        'minimum_age': policy.MINIMUM_AGE,
        'session_days': settings.SESSION_COOKIE_AGE // 86400,
        'csrf_days': settings.CSRF_COOKIE_AGE // 86400,
        'theme_days': THEME_COOKIE_MAX_AGE // 86400,
    }


def privacy(request):
    return render(request, 'legal/privacy.html', _context())


def terms(request):
    return render(request, 'legal/terms.html', _context())
