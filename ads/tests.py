import io
import os
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Ad, AdImage, Category, Tag


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


def make_image(name='photo.png'):
    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), 'teal').save(buffer, 'PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class EditAndImageTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user('alice', password='pw-12345!')
        User.objects.create_user('bob', password='pw-12345!')
        self.category = Category.objects.create(name='Furniture')
        self.ad = Ad.objects.create(owner=self.user, title='Desk', description='Oak', category=self.category)
        self.client.login(username='alice', password='pw-12345!')

    def form_data(self, **overrides):
        data = {'title': 'Desk', 'description': 'Oak', 'category': self.category.pk, 'tag_names': ''}
        data.update(overrides)
        return data

    def test_owner_can_edit_ad(self):
        response = self.client.post(
            reverse('ads:edit', args=[self.ad.pk]),
            self.form_data(title='Oak desk', price='80', tag_names='wood'),
        )
        self.assertRedirects(response, self.ad.get_absolute_url())
        self.ad.refresh_from_db()
        self.assertEqual(self.ad.title, 'Oak desk')
        self.assertEqual([t.name for t in self.ad.tags.all()], ['wood'])

    def test_edit_form_prefills_tags(self):
        self.ad.tags.add(Tag.objects.create(name='antique'))
        self.assertContains(self.client.get(reverse('ads:edit', args=[self.ad.pk])), 'value="antique"')

    def test_non_owner_cannot_edit_ad(self):
        self.client.login(username='bob', password='pw-12345!')
        response = self.client.post(reverse('ads:edit', args=[self.ad.pk]), self.form_data(title='Hacked'))
        self.assertEqual(response.status_code, 404)
        self.ad.refresh_from_db()
        self.assertEqual(self.ad.title, 'Desk')

    def test_create_ad_with_images(self):
        response = self.client.post(reverse('ads:create'), self.form_data(
            title='Chair', images=[make_image('a.png'), make_image('b.png')],
        ))
        ad = Ad.objects.get(title='Chair')
        self.assertRedirects(response, ad.get_absolute_url())
        self.assertEqual(ad.images.count(), 2)
        self.assertContains(self.client.get(ad.get_absolute_url()), ad.images.first().image.url)

    def test_more_than_three_images_rejected(self):
        response = self.client.post(reverse('ads:create'), self.form_data(
            title='Chair', images=[make_image() for _ in range(4)],
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'at most 3 images')
        self.assertFalse(Ad.objects.filter(title='Chair').exists())

    def test_edit_limit_counts_existing_images(self):
        for _ in range(2):
            AdImage.objects.create(ad=self.ad, image=make_image())
        url = reverse('ads:edit', args=[self.ad.pk])
        response = self.client.post(url, self.form_data(images=[make_image(), make_image()]))
        self.assertContains(response, 'at most 3 images')
        self.assertEqual(self.ad.images.count(), 2)

        # Removing one existing image makes room for two new ones.
        remove = self.ad.images.first()
        response = self.client.post(url, self.form_data(
            images=[make_image(), make_image()], remove_images=[remove.pk],
        ))
        self.assertRedirects(response, self.ad.get_absolute_url())
        self.assertEqual(self.ad.images.count(), 3)
        self.assertFalse(self.ad.images.filter(pk=remove.pk).exists())

    def test_cannot_remove_another_ads_image(self):
        other_ad = Ad.objects.create(owner=self.user, title='Lamp', description='x', category=self.category)
        other_image = AdImage.objects.create(ad=other_ad, image=make_image())
        response = self.client.post(
            reverse('ads:edit', args=[self.ad.pk]), self.form_data(remove_images=[other_image.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AdImage.objects.filter(pk=other_image.pk).exists())

    def test_non_image_upload_rejected(self):
        bogus = SimpleUploadedFile('notes.png', b'not an image', content_type='image/png')
        response = self.client.post(reverse('ads:create'), self.form_data(title='Chair', images=[bogus]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Ad.objects.filter(title='Chair').exists())

    def test_deleting_ad_deletes_image_files(self):
        image = AdImage.objects.create(ad=self.ad, image=make_image())
        path = image.image.path
        self.assertTrue(os.path.exists(path))
        self.client.post(reverse('ads:delete', args=[self.ad.pk]))
        self.assertFalse(os.path.exists(path))

    def test_photo_grids_show_every_photo(self):
        images = [AdImage.objects.create(ad=self.ad, image=make_image()) for _ in range(3)]
        home = self.client.get(reverse('ads:list'))
        detail = self.client.get(self.ad.get_absolute_url())
        self.assertContains(home, 'photo-grid photos-3')
        self.assertContains(detail, 'photo-grid photos-3 large')
        for image in images:
            self.assertContains(home, image.image.url)
            self.assertContains(detail, f'href="{image.image.url}" class="photo" data-lightbox')

    def test_listing_without_photos_shows_placeholder(self):
        self.assertContains(self.client.get(reverse('ads:list')), 'No photos')
        self.assertNotContains(self.client.get(self.ad.get_absolute_url()), 'class="photo-grid')

    def test_image_urls_avoid_ad_blocker_patterns(self):
        # Ad blockers hide images whose URL contains "/ads/".
        image = AdImage.objects.create(ad=self.ad, image=make_image())
        self.assertNotIn('/ads/', image.image.url)
