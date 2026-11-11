import io
import os
import shutil
import tempfile
import time
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import geocoding
from .geocoding import GeocodingUnavailable, Place
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

    def test_static_assets_are_versioned(self):
        # site.css/site.js links carry ?v=<mtime> so browsers fetch them again after a change.
        html = self.client.get(reverse('ads:list')).content.decode()
        self.assertRegex(html, r'/static/css/site\.css\?v=\d+"')
        self.assertRegex(html, r'/static/js/site\.js\?v=\d+"')

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
        # London to Paris is ~213 miles (~344 km), so 250 only includes it if the radius is in miles.
        response = self.client.get(reverse('ads:list'), {**near, 'radius': 250})
        self.assertContains(response, 'Paris scooter')
        self.assertContains(response, 'mi away')
        self.assertNotContains(response, 'km away')

    def test_distance_is_in_miles(self):
        self.assertAlmostEqual(self.ad.distance_miles(48.8566, 2.3522), 213.5, delta=1)

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


def make_image(name='photo.png', fmt='PNG', size=(10, 10), **save_args):
    buffer = io.BytesIO()
    Image.new('RGB', size, 'teal').save(buffer, fmt, **save_args)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f'image/{fmt.lower()}')


def jpeg_with_gps(name='IMG_1234_home.jpg'):
    exif = Image.Exif()
    exif[0x010F] = 'PhoneMaker'  # camera make
    exif[0x8825] = {1: 'N', 2: (37.0, 46.0, 30.0), 3: 'W', 4: (122.0, 25.0, 10.0)}  # GPS IFD
    return make_image(name, 'JPEG', size=(50, 40), exif=exif)


OAKLAND = Place(37.8044, -122.2714, 'Oakland, Alameda County, California')


class LocationSearchTests(TestCase):
    """Search by a typed location name; the geocoder is mocked so no network is used."""

    def setUp(self):
        user = User.objects.create_user('carol', password='pw-12345!')
        cat = Category.objects.create(name='For Sale')
        Ad.objects.create(owner=user, title='Berkeley lamp', description='x', category=cat,
                          latitude=37.8716, longitude=-122.2727)  # ~4.7 mi from Oakland
        Ad.objects.create(owner=user, title='San Jose desk', description='x', category=cat,
                          latitude=37.3382, longitude=-121.8863)  # ~38 mi from Oakland

    def search(self, **params):
        return self.client.get(reverse('ads:list'), params)

    @mock.patch('ads.forms.geocode', return_value=OAKLAND)
    def test_location_and_radius(self, geocode):
        response = self.search(near='Oakland, CA', radius=10)
        geocode.assert_called_once_with('Oakland, CA', client='127.0.0.1')
        self.assertContains(response, 'Berkeley lamp')
        self.assertNotContains(response, 'San Jose desk')
        self.assertContains(response, 'Showing ads within 10 mi of')
        self.assertContains(response, '<strong>Oakland, Alameda County, California</strong>')
        self.assertContains(response, 'value="Oakland, CA"')  # the field keeps what was typed

    @mock.patch('ads.forms.geocode', return_value=OAKLAND)
    def test_location_without_radius_sorts_by_distance(self, geocode):
        content = self.search(near='Oakland').content.decode()
        self.assertLess(content.index('Berkeley lamp'), content.index('San Jose desk'))

    @mock.patch('ads.forms.geocode', return_value=OAKLAND)
    def test_typed_location_overrides_coordinates(self, geocode):
        # Coordinates for London, but the typed location (Oakland) should win.
        response = self.search(near='Oakland', lat=51.5, lng=-0.12, radius=10)
        self.assertContains(response, 'Berkeley lamp')

    @mock.patch('ads.forms.geocode', return_value=None)
    def test_unknown_location(self, geocode):
        response = self.search(near='Nowhereville', radius=10)
        self.assertContains(response, 'find \u201cNowhereville\u201d')
        self.assertContains(response, 'San Jose desk')  # no location filter applied

    @mock.patch('ads.forms.geocode', side_effect=GeocodingUnavailable('timeout'))
    def test_geocoder_unavailable(self, geocode):
        response = self.search(near='Oakland')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Location search is unavailable')

    @mock.patch('ads.forms.geocode', side_effect=GeocodingUnavailable('timeout'))
    def test_failed_location_keeps_the_other_filters(self, geocode):
        response = self.search(q='lamp', near='Oakland')
        self.assertContains(response, 'Berkeley lamp')
        self.assertNotContains(response, 'San Jose desk')

    @mock.patch('ads.forms.geocode', side_effect=geocoding.GeocodingRateLimited('slow down'))
    def test_rate_limited_message(self, geocode):
        self.assertContains(self.search(near='Oakland'), 'searched for a lot of new places')

    @mock.patch('ads.forms.geocode', return_value=OAKLAND)
    def test_radius_is_capped(self, geocode):
        response = self.search(near='Oakland', radius=5000)
        self.assertContains(response, 'less than or equal to 500')

    @mock.patch('ads.forms.geocode', return_value=OAKLAND)
    def test_search_area_and_pages_of_nearest_ads(self, geocode):
        user = User.objects.first()
        cat = Category.objects.first()
        Ad.objects.create(owner=user, title='New York sofa', description='x', category=cat,
                          latitude=40.71, longitude=-74.0)  # ~2,570 mi away: outside the 500 mi area
        for i in range(13):  # 13 more ads 0.1 mi apart, heading north from Oakland
            Ad.objects.create(owner=user, title=f'Item {i:02d}', description='x', category=cat,
                              latitude=37.8044 + 0.0015 * (i + 1), longitude=-122.2714)
        first = self.search(near='Oakland')
        self.assertContains(first, 'Showing ads within 500 mi of')
        self.assertNotContains(first, 'New York sofa')
        self.assertEqual(first.context['page'].paginator.count, 15)
        self.assertEqual([ad.title for ad in first.context['page'].object_list][:2], ['Item 00', 'Item 01'])
        last = self.search(near='Oakland', page=2).context['page'].object_list
        self.assertEqual([ad.title for ad in last], ['Item 12', 'Berkeley lamp', 'San Jose desk'])
        self.assertAlmostEqual(last[-1].distance, 38, delta=1)
        self.assertContains(first, 'href="?near=Oakland&amp;page=2"')

    def test_pagination_link_without_filters(self):
        user, cat = User.objects.first(), Category.objects.first()
        for i in range(12):
            Ad.objects.create(owner=user, title=f'Extra {i}', description='x', category=cat)
        self.assertContains(self.search(), 'href="?page=2"')

    def test_client_ip_trusts_forwarded_header_only_behind_proxy(self):
        from django.test import RequestFactory
        from .ratelimit import client_ip
        request = RequestFactory().get('/', REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR='6.6.6.6, 203.0.113.9')
        self.assertEqual(client_ip(request), '10.0.0.1')
        with self.settings(BEHIND_PROXY=True):
            self.assertEqual(client_ip(request), '203.0.113.9')


class GeocodeTests(TestCase):
    def setUp(self):
        cache.clear()
        patcher = mock.patch('ads.geocoding._sleep')  # don't really wait for the next free second
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_response(self, payload):
        response = mock.MagicMock()
        response.__enter__.return_value = io.BytesIO(payload.encode())
        return response

    @mock.patch('ads.geocoding.urllib.request.urlopen')
    def test_result_is_parsed_and_cached(self, urlopen):
        urlopen.return_value = self.fake_response(
            '[{"lat": "37.80", "lon": "-122.27", "display_name": "Oakland, Alameda County, California, United States"}]')
        place = geocoding.geocode('  Oakland,   CA ')
        self.assertEqual(place, Place(37.80, -122.27, 'Oakland, Alameda County, California'))
        self.assertEqual(geocoding.geocode('oakland, ca'), place)  # cached: no second request
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args[0][0]
        self.assertIn('q=Oakland%2C+CA', request.full_url)
        self.assertIn('addressdetails=1', request.full_url)
        self.assertNotIn('countrycodes', request.full_url)
        self.assertIn('classifieds-django-app', request.get_header('User-agent'))

    @mock.patch('ads.geocoding.urllib.request.urlopen')
    def test_place_preferred_over_business(self, urlopen):
        urlopen.return_value = self.fake_response('''[
            {"lat": "37.1", "lon": "-122.1", "category": "amenity", "display_name": "Cafe Mission, 1 Main St"},
            {"lat": "37.76", "lon": "-122.42", "category": "place", "display_name": "Mission, San Francisco, California, 94110"}]''')
        self.assertEqual(geocoding.geocode('Mission'), Place(37.76, -122.42, 'Mission, San Francisco, California'))

    @mock.patch('ads.geocoding.urllib.request.urlopen')
    def test_business_only_shows_area_name(self, urlopen):
        urlopen.return_value = self.fake_response('''[{"lat": "37.77", "lon": "-122.41", "category": "amenity",
            "display_name": "Revel - Mission District, 199, Erie Street, Mission, San Francisco",
            "address": {"amenity": "Revel - Mission District", "road": "Erie Street", "neighbourhood": "Mission",
                        "city": "San Francisco", "state": "California", "country": "United States"}}]''')
        place = geocoding.geocode('Mission District, San Francisco')
        self.assertEqual(place, Place(37.77, -122.41, 'Mission, San Francisco, California'))

    @mock.patch('ads.geocoding.urllib.request.urlopen')
    def test_zip_code_is_looked_up_in_the_us(self, urlopen):
        urlopen.return_value = self.fake_response('[]')
        geocoding.geocode('94301')
        self.assertIn('countrycodes=us', urlopen.call_args[0][0].full_url)

    @mock.patch('ads.geocoding.urllib.request.urlopen')
    def test_no_match_returns_none(self, urlopen):
        urlopen.return_value = self.fake_response('[]')
        self.assertIsNone(geocoding.geocode('Nowhereville'))

    @mock.patch('ads.geocoding.urllib.request.urlopen', side_effect=geocoding.urllib.error.URLError('down'))
    def test_network_error_raises(self, urlopen):
        with self.assertRaises(GeocodingUnavailable):
            geocoding.geocode('Oakland')

    def test_every_kind_of_failure_is_reported_as_unavailable(self):
        import http.client
        failures = [http.client.RemoteDisconnected('closed'), http.client.IncompleteRead(b''), TimeoutError()]
        for exc in failures:
            with self.subTest(exc=type(exc).__name__), mock.patch(
                    'ads.geocoding.urllib.request.urlopen', side_effect=exc):
                cache.clear()
                with self.assertRaises(GeocodingUnavailable):
                    geocoding.geocode('Oakland')
        for payload in ('{"error": "x"}', '[{"lon": "1"}]', '[{"lat": "north", "lon": "1"}]', 'not json'):
            with self.subTest(payload=payload), mock.patch('ads.geocoding.urllib.request.urlopen',
                                                           return_value=self.fake_response(payload)):
                cache.clear()
                with self.assertRaises(GeocodingUnavailable):
                    geocoding.geocode('Oakland')

    @mock.patch('ads.geocoding._reserve_slot')
    @mock.patch('ads.geocoding.urllib.request.urlopen')
    def test_new_lookups_are_rate_limited_per_client(self, urlopen, reserve_slot):
        urlopen.side_effect = lambda *args, **kwargs: self.fake_response('[]')
        limit = geocoding.CLIENT_LIMITS[0][0]
        for i in range(limit):
            geocoding.geocode(f'place {i}', client='1.2.3.4')
        with self.assertRaises(geocoding.GeocodingRateLimited):
            geocoding.geocode('one more place', client='1.2.3.4')
        geocoding.geocode('place 0', client='1.2.3.4')  # cached answers are always fine
        self.assertEqual(urlopen.call_count, limit)

    @mock.patch('ads.geocoding.urllib.request.urlopen')
    def test_fails_fast_when_every_slot_is_taken(self, urlopen):
        now = int(time.time())
        for second in range(now, now + geocoding.MAX_WAIT_SECONDS + 3):
            cache.set(f'geocode:slot:{second}', 1)
        with self.assertRaises(geocoding.GeocodingBusy):
            geocoding.geocode('Oakland')
        urlopen.assert_not_called()

    @mock.patch('ads.geocoding.urllib.request.urlopen')
    def test_requests_are_at_least_a_second_apart(self, urlopen):
        urlopen.side_effect = lambda *args, **kwargs: self.fake_response('[]')
        starts = []
        with mock.patch('ads.geocoding._sleep', side_effect=lambda wait: starts.append(time.time() + wait)):
            for i in range(3):
                geocoding.geocode(f'town {i}')
        self.assertEqual(len(starts), 3)
        self.assertTrue(all(b - a >= 0.999 for a, b in zip(starts, starts[1:])), starts)


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
        image = AdImage.create_from_file(self.ad, make_image())
        paths = [image.image.path, image.thumbnail.path]
        self.assertTrue(all(os.path.exists(p) for p in paths))
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('ads:delete', args=[self.ad.pk]))
        self.assertFalse(any(os.path.exists(p) for p in paths))

    def test_files_survive_a_rolled_back_delete(self):
        from django.db import transaction
        image = AdImage.objects.create(ad=self.ad, image=make_image())
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    image.delete()
                    raise RuntimeError('boom')
            except RuntimeError:
                pass
        self.assertTrue(os.path.exists(image.image.path))

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


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SeedAdsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def seed(self, *args):
        call_command('seed_ads', *args, stdout=io.StringIO())

    def test_creates_demo_ads_with_photos_and_locations(self):
        from .management.commands.seed_ads import DEMO_ADS
        self.seed()
        ads = Ad.objects.filter(owner__username='bayarea_demo')
        self.assertEqual(ads.count(), len(DEMO_ADS))
        self.assertFalse(User.objects.get(username='bayarea_demo').has_usable_password())
        self.assertEqual(len({ad.category.parent_id for ad in ads}), len(DEMO_ADS))  # one per top-level category
        for ad in ads:
            self.assertTrue(ad.has_coordinates)
            self.assertGreaterEqual(ad.images.count(), 2, ad.title)
            for image in ad.images.all():
                self.assertTrue(os.path.exists(image.image.path))
                self.assertNotIn('/ads/', image.image.url)  # ad blockers hide those paths

    def test_is_idempotent_and_fresh_recreates(self):
        self.seed()
        first_ids = set(Ad.objects.values_list('pk', flat=True))
        self.seed()
        self.assertEqual(set(Ad.objects.values_list('pk', flat=True)), first_ids)
        old_file = AdImage.objects.first().image.path
        with self.captureOnCommitCallbacks(execute=True):
            self.seed('--fresh')
        self.assertEqual(Ad.objects.count(), len(first_ids))
        self.assertTrue(first_ids.isdisjoint(Ad.objects.values_list('pk', flat=True)))
        self.assertFalse(os.path.exists(old_file))  # replaced ads' photos are cleaned up

    def test_every_bundled_photo_exists_and_is_credited(self):
        from .management.commands.seed_ads import DEMO_ADS, PHOTO_DIR
        credits = (PHOTO_DIR.parent / 'CREDITS.md').read_text()
        listed = [p for spec in DEMO_ADS for p in spec['photos']]
        self.assertEqual({p['file'] for p in listed}, {f.name for f in PHOTO_DIR.glob('*.jpg')})
        for p in listed:
            self.assertTrue(p['author'] and p['licence'] and p['source'].startswith('https://'), p['file'])
            self.assertIn(f"`{p['file']}`", credits)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PhotoPrivacyTests(TestCase):
    """Uploads are re-encoded: no metadata, random names, size caps, thumbnails."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user('alice', password='pw-12345!')
        self.category = Category.objects.create(name='Furniture')
        self.client.login(username='alice', password='pw-12345!')

    def post(self, **data):
        base = {'title': 'Chair', 'description': 'x', 'category': self.category.pk, 'tag_names': ''}
        base.update(data)
        return self.client.post(reverse('ads:create'), base)

    def test_upload_metadata_is_stripped_and_name_randomised(self):
        upload = jpeg_with_gps()
        self.assertIn(0x8825, Image.open(io.BytesIO(upload.read())).getexif())  # the fixture has GPS
        upload.seek(0)
        self.post(images=[upload])
        image = Ad.objects.get(title='Chair').images.get()
        for field in (image.image, image.thumbnail):
            with Image.open(field.path) as stored:
                self.assertEqual(stored.format, 'JPEG')
                self.assertEqual(len(stored.getexif()), 0)
                self.assertNotIn('icc_profile', stored.info)
            self.assertNotIn('IMG_1234', field.name)
        self.assertNotIn('IMG_1234', self.client.get(image.ad.get_absolute_url()).content.decode())

    def test_large_photos_are_resized_and_listings_use_thumbnails(self):
        self.post(images=[make_image('big.png', size=(3000, 1500))])
        image = Ad.objects.get(title='Chair').images.get()
        with Image.open(image.image.path) as stored:
            self.assertEqual(max(stored.size), 2000)
        with Image.open(image.thumbnail.path) as thumb:
            self.assertEqual(max(thumb.size), 640)
        home = self.client.get(reverse('ads:list')).content.decode()
        self.assertIn(image.thumbnail.url, home)
        self.assertNotIn(f'src="{image.image.url}"', home)

    def test_only_jpeg_png_and_webp_are_accepted(self):
        response = self.post(images=[make_image('photo.png', 'GIF')])  # a GIF named .png
        self.assertContains(response, 'not a JPG, PNG or WebP photo')
        self.assertFalse(Ad.objects.exists())
        self.post(images=[make_image('ok.webp', 'WEBP')])
        self.assertEqual(Ad.objects.get().images.count(), 1)

    def test_oversized_file_rejected_before_parsing(self):
        big = SimpleUploadedFile('huge.jpg', b'x' * (5 * 1024 * 1024 + 1), content_type='image/jpeg')
        self.assertContains(self.post(images=[big]), 'larger than 5 MB')
        self.assertFalse(Ad.objects.exists())

    def test_too_many_pixels_rejected(self):
        with mock.patch('ads.images.MAX_PIXELS', 50):
            response = self.post(images=[make_image(size=(10, 10))])
        self.assertContains(response, 'is too large')
        self.assertFalse(Ad.objects.exists())

    def test_coordinates_are_rounded(self):
        self.post(latitude='37.774929', longitude='-122.419416')
        ad = Ad.objects.get()
        self.assertEqual((ad.latitude, ad.longitude), (37.775, -122.419))
        self.assertContains(self.client.get(ad.get_absolute_url()), 'data-lat="37.775000"')

    def test_reprocess_command_cleans_old_uploads(self):
        ad = Ad.objects.create(owner=self.user, title='Old', description='x', category=self.category)
        old = AdImage.objects.create(ad=ad, image=jpeg_with_gps())
        old_path = old.image.path
        with self.captureOnCommitCallbacks(execute=True):
            call_command('reprocess_images', stdout=io.StringIO())
        old.refresh_from_db()
        self.assertTrue(old.thumbnail)
        self.assertFalse(os.path.exists(old_path))
        with Image.open(old.image.path) as stored:
            self.assertEqual(len(stored.getexif()), 0)


class CorrectnessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='pw-12345!')
        self.parent = Category.objects.create(name='For Sale')
        self.sub = Category.objects.create(name='Books', parent=self.parent)
        self.client.login(username='alice', password='pw-12345!')

    def post_ad(self, **data):
        base = {'title': 'Book', 'description': 'x', 'category': self.sub.pk, 'tag_names': ''}
        base.update(data)
        return self.client.post(reverse('ads:create'), base)

    def test_tags_that_slugify_alike_stay_separate(self):
        self.post_ad(title='One', tag_names='c++')
        self.post_ad(title='Two', tag_names='c#, c++')
        self.assertEqual(sorted(Tag.objects.values_list('name', 'slug')), [('c#', 'c-2'), ('c++', 'c')])
        two = Ad.objects.get(title='Two')
        self.assertEqual(sorted(t.name for t in two.tags.all()), ['c#', 'c++'])
        self.assertEqual(Tag.objects.get(name='c++').ads.count(), 2)  # existing tag reused by name

    def test_category_hierarchy_is_two_levels_without_loops(self):
        from django.core.exceptions import ValidationError
        self.parent.parent = self.parent
        with self.assertRaisesMessage(ValidationError, 'its own parent'):
            self.parent.full_clean()
        self.parent.parent = self.sub
        with self.assertRaisesMessage(ValidationError, 'top-level'):
            self.parent.full_clean()
        other = Category.objects.create(name='Vehicles')
        self.parent.parent = other
        with self.assertRaisesMessage(ValidationError, 'has subcategories'):
            self.parent.full_clean()

    def test_category_slugs_are_unique(self):
        a = Category.objects.create(name='Misc Stuff')
        b = Category.objects.create(name='Stuff', parent=Category.objects.create(name='Misc'))
        self.assertEqual((a.slug, b.slug), ('misc-stuff', 'misc-stuff-2'))

    def test_negative_price_rejected(self):
        response = self.post_ad(price='-50')
        self.assertContains(response, 'greater than or equal to 0')
        self.assertFalse(Ad.objects.exists())

    def test_edit_heading_shows_saved_title_after_invalid_submit(self):
        ad = Ad.objects.create(owner=self.user, title='Old title', description='x', category=self.sub)
        response = self.client.post(reverse('ads:edit', args=[ad.pk]), {
            'title': 'New title', 'description': '', 'category': self.sub.pk, 'tag_names': ''})
        self.assertContains(response, 'Edit \u201cOld title\u201d')
        self.assertNotContains(response, 'Edit \u201cNew title\u201d')

    def test_failed_photo_save_rolls_back_the_new_ad(self):
        with mock.patch.object(AdImage, 'create_from_file', side_effect=OSError('disk full')):
            with self.assertRaises(OSError), self.assertLogs('django.request', 'ERROR'):
                self.post_ad(images=[make_image()])
        self.assertFalse(Ad.objects.exists())

    def test_seed_refuses_to_use_a_real_account(self):
        from django.core.management.base import CommandError
        User.objects.create_user('bayarea_demo', password='pw-12345!')
        with self.assertRaisesMessage(CommandError, 'real account'):
            call_command('seed_ads', stdout=io.StringIO())
        self.assertFalse(Ad.objects.exists())
