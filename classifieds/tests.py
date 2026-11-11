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
