"""Security headers that Django doesn't set itself."""

# Everything is served from this site; the only third party is OpenStreetMap's tiles.
# No inline scripts or style attributes are allowed (templates use classes and
# static/js/site.js), which blocks most injected-content attacks even if one slipped in.
CONTENT_SECURITY_POLICY = '; '.join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data: blob: https://tile.openstreetmap.org",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
# Django's admin templates use inline style attributes.
ADMIN_CONTENT_SECURITY_POLICY = CONTENT_SECURITY_POLICY.replace("style-src 'self'", "style-src 'self' 'unsafe-inline'")
PERMISSIONS_POLICY = 'geolocation=(self), camera=(), microphone=(), payment=(), usb=()'


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = ADMIN_CONTENT_SECURITY_POLICY if request.path.startswith('/admin/') else CONTENT_SECURITY_POLICY
        response.headers.setdefault('Content-Security-Policy', policy)
        response.headers.setdefault('Permissions-Policy', PERMISSIONS_POLICY)
        return response
