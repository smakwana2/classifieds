from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from ads.models import Ad, Category


class AccountTests(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache

    def test_signup_logs_user_in(self):
        response = self.client.post(reverse('signup'), {
            'username': 'carol', 'email': 'carol@example.com',
            'password1': 'Sup3r-secret-pw', 'password2': 'Sup3r-secret-pw',
        })
        self.assertRedirects(response, reverse('ads:list'))
        self.assertTrue(User.objects.filter(username='carol').exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='carol').pk)

    def test_delete_account_requires_correct_password(self):
        user = User.objects.create_user('dave', password='pw-12345!')
        self.client.login(username='dave', password='pw-12345!')
        response = self.client.post(reverse('delete_account'), {'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_delete_account_removes_user_and_ads(self):
        user = User.objects.create_user('erin', password='pw-12345!')
        Ad.objects.create(owner=user, title='Lamp', description='x', category=Category.objects.create(name='Home'))
        self.client.login(username='erin', password='pw-12345!')
        response = self.client.post(reverse('delete_account'), {'password': 'pw-12345!'})
        self.assertRedirects(response, reverse('ads:list'))
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(Ad.objects.exists())
        self.assertNotIn('_auth_user_id', self.client.session)


class AbuseProtectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('frank', password='pw-12345!')

    def login(self, password):
        return self.client.post(reverse('login'), {'username': 'frank', 'password': password})

    def test_login_is_throttled_after_repeated_failures(self):
        for _ in range(10):
            self.assertEqual(self.login('wrong').status_code, 200)
        response = self.login('pw-12345!')  # even the right password is refused for now
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'Too many failed attempts', status_code=429)
        self.assertNotIn('_auth_user_id', self.client.session)
        cache.clear()  # the window has passed
        self.assertRedirects(self.login('pw-12345!'), reverse('ads:list'))

    def test_delete_account_password_is_throttled(self):
        self.client.login(username='frank', password='pw-12345!')
        for _ in range(5):
            self.client.post(reverse('delete_account'), {'password': 'wrong'})
        response = self.client.post(reverse('delete_account'), {'password': 'pw-12345!'})
        self.assertContains(response, 'Too many failed attempts')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def signup(self, username):
        return self.client.post(reverse('signup'), {
            'username': username, 'password1': 'Sup3r-secret-pw', 'password2': 'Sup3r-secret-pw'})

    def test_signups_are_limited_per_ip(self):
        for i in range(5):
            self.signup(f'user{i}')
            self.client.logout()
        self.assertContains(self.signup('user5'), 'Too many accounts')
        self.assertFalse(User.objects.filter(username='user5').exists())

    def test_lookalike_and_non_ascii_usernames_rejected(self):
        self.assertContains(self.signup('FRANK'), 'already exists')
        self.assertContains(self.signup('fr\u0430nk'), 'Use 3')  # Cyrillic "a"
        self.assertFalse(User.objects.exclude(pk=self.user.pk).exists())

    def test_password_reset_is_not_offered(self):
        self.assertEqual(self.client.get('/accounts/password_reset/').status_code, 404)
