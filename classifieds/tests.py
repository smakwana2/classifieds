import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent
PRINT_SETTINGS = (
    'import django; django.setup(); from django.conf import settings as s; '
    'print(s.DEBUG, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, s.SECURE_SSL_REDIRECT, '
    'bool(s.SECURE_HSTS_SECONDS), s.ALLOWED_HOSTS)'
)


class SettingsFailSafeTests(SimpleTestCase):
    """Settings are loaded in a fresh process so the environment can be controlled."""

    def load(self, **env):
        base = {'PATH': os.environ.get('PATH', ''), 'DJANGO_SETTINGS_MODULE': 'classifieds.settings'}
        return subprocess.run([sys.executable, '-c', PRINT_SETTINGS], cwd=BASE_DIR, env={**base, **env},
                              capture_output=True, text=True, timeout=60)

    def test_refuses_to_start_without_secret_key_when_not_debugging(self):
        result = self.load()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set DJANGO_SECRET_KEY', result.stderr)

    def test_production_defaults_are_secure(self):
        result = self.load(DJANGO_SECRET_KEY='x' * 50, DJANGO_ALLOWED_HOSTS=' example.com , www.example.com ')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False True True True True ['example.com', 'www.example.com']")

    def test_debug_mode_for_local_development(self):
        result = self.load(DJANGO_DEBUG='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith('True False False'))


class SecurityHeaderTests(SimpleTestCase):
    def test_pages_send_csp_and_permissions_policy(self):
        response = self.client.get('/accounts/login/')
        csp = response.headers['Content-Security-Policy']
        self.assertIn("script-src 'self';", csp)
        self.assertIn("style-src 'self';", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn('geolocation=(self)', response.headers['Permissions-Policy'])

    def test_templates_have_no_inline_code_or_third_party_assets(self):
        # The CSP would block these; keep scripts in static/js and styles in classes.
        import re
        for path in (BASE_DIR / 'templates').rglob('*.html'):
            html = path.read_text()
            with self.subTest(template=str(path.relative_to(BASE_DIR))):
                self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)[^>]*>', 'inline <script>')
                self.assertNotIn('style="', html)
                self.assertNotRegex(html, r'\son[a-z]+="', 'inline event handler')
                self.assertIsNone(re.search(r'(src|href)="https?://(?!www\.openstreetmap\.org)', html))
