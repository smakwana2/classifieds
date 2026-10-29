from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ads.models import Ad, Category


class AccountTests(TestCase):
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
