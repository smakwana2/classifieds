from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Ad, Category, Tag


class AdTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='pw-12345!')
        self.other = User.objects.create_user('bob', password='pw-12345!')
        self.parent = Category.objects.create(name='Vehicles')
        self.sub = Category.objects.create(name='Bicycles', parent=self.parent)
        self.ad = Ad.objects.create(
            owner=self.user, title='Road bike', description='Fast.', price=300,
            category=self.sub, location_name='London', latitude=51.5074, longitude=-0.1278,
        )

    def test_category_slugs_and_hierarchy(self):
        self.assertEqual(self.sub.slug, 'vehicles-bicycles')
        self.assertEqual(set(self.parent.self_and_descendant_ids()), {self.parent.pk, self.sub.pk})

    def test_list_and_detail(self):
        self.assertContains(self.client.get(reverse('ads:list')), 'Road bike')
        self.assertContains(self.client.get(self.ad.get_absolute_url()), 'Fast.')

    def test_parent_category_includes_subcategory_ads(self):
        self.assertContains(self.client.get(self.parent.get_absolute_url()), 'Road bike')

    def test_categories_page(self):
        response = self.client.get(reverse('ads:categories'))
        self.assertContains(response, 'Vehicles')
        self.assertContains(response, 'Bicycles')

    def test_search(self):
        self.assertContains(self.client.get(reverse('ads:list'), {'q': 'road'}), 'Road bike')
        self.assertNotContains(self.client.get(reverse('ads:list'), {'q': 'sofa'}), 'Road bike')

    def test_nearby_filter(self):
        Ad.objects.create(owner=self.user, title='Paris scooter', description='x', category=self.sub,
                          latitude=48.8566, longitude=2.3522)
        near = {'lat': 51.5, 'lng': -0.12, 'radius': 50}
        response = self.client.get(reverse('ads:list'), near)
        self.assertContains(response, 'Road bike')
        self.assertNotContains(response, 'Paris scooter')
        response = self.client.get(reverse('ads:list'), {**near, 'radius': 500})
        self.assertContains(response, 'Paris scooter')

    def test_post_ad_requires_login(self):
        response = self.client.get(reverse('ads:create'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('ads:create')}")

    def test_post_ad_with_tags(self):
        self.client.login(username='alice', password='pw-12345!')
        response = self.client.post(reverse('ads:create'), {
            'title': 'Old sofa', 'description': 'Comfy', 'price': '50', 'category': self.parent.pk,
            'tag_names': 'Vintage, bargain, vintage', 'location_name': 'Leeds',
            'latitude': '53.8', 'longitude': '-1.55',
        })
        ad = Ad.objects.get(title='Old sofa')
        self.assertRedirects(response, ad.get_absolute_url())
        self.assertEqual(ad.owner, self.user)
        self.assertEqual(sorted(t.name for t in ad.tags.all()), ['bargain', 'vintage'])
        self.assertContains(self.client.get(reverse('ads:tag', args=['vintage'])), 'Old sofa')

    def test_post_ad_rejects_half_coordinates(self):
        self.client.login(username='alice', password='pw-12345!')
        response = self.client.post(reverse('ads:create'), {
            'title': 'X', 'description': 'Y', 'category': self.sub.pk, 'latitude': '10',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Ad.objects.filter(title='X').exists())

    def test_owner_can_delete_ad(self):
        self.client.login(username='alice', password='pw-12345!')
        response = self.client.post(reverse('ads:delete', args=[self.ad.pk]))
        self.assertRedirects(response, reverse('ads:my_ads'))
        self.assertFalse(Ad.objects.filter(pk=self.ad.pk).exists())

    def test_non_owner_cannot_delete_ad(self):
        self.client.login(username='bob', password='pw-12345!')
        response = self.client.post(reverse('ads:delete', args=[self.ad.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Ad.objects.filter(pk=self.ad.pk).exists())

    def test_seed_categories_is_idempotent(self):
        call_command('seed_categories', verbosity=0)
        count = Category.objects.count()
        call_command('seed_categories', verbosity=0)
        self.assertEqual(Category.objects.count(), count)
        self.assertTrue(Category.objects.filter(name='Cars', parent__name='Vehicles').exists())

    def test_tag_slug(self):
        self.assertEqual(Tag.objects.create(name='Like New').slug, 'like-new')
