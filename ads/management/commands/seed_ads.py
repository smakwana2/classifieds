"""Create demo ads around the San Francisco Bay Area, with real photos.

The photos are bundled in ads/seed_data/photos/ (Wikimedia Commons, freely
licensed; see ads/seed_data/CREDITS.md), so seeding works offline. Ads are
owned by a demo user that cannot log in; delete that user to remove them all.
"""
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ads.models import Ad, AdImage, Category, Tag

PHOTO_DIR = Path(__file__).resolve().parents[2] / 'seed_data' / 'photos'
DEMO_USERNAME = 'bayarea_demo'


def photo(file, title, author, licence, source):
    return {'file': file, 'title': title, 'author': author, 'licence': licence, 'source': source}


COMMONS = 'https://commons.wikimedia.org/wiki/File:'

DEMO_ADS = [
    {
        'title': 'Sony A7 III mirrorless camera body',
        'category': ('For Sale', 'Electronics'),
        'price': '1150',
        'description': 'Lightly used full-frame body, ~8k shutter count. Comes with two batteries, charger '
                       'and original box. No scratches on the sensor.',
        'location': 'Mission District, San Francisco', 'lat': 37.7599, 'lng': -122.4148,
        'tags': ['camera', 'photography', 'sony'],
        'photos': [
            photo('camera-1.jpg', 'Sony Alpha7 III 20 apr 2018f', '昼落ち', 'CC BY-SA 4.0',
                  COMMONS + 'Sony_Alpha7_III_20_apr_2018f.jpg'),
            photo('camera-2.jpg', 'Sony A 7 iii full frame mirrorless camera', 'Amitabha Gupta', 'CC BY 4.0',
                  COMMONS + 'Sony_A_7_iii_full_frame_mirrorless_camera.jpg'),
            photo('camera-3.jpg', 'Sony Alpha7 III 20 apr 2018d', '昼落ち', 'CC BY-SA 4.0',
                  COMMONS + 'Sony_Alpha7_III_20_apr_2018d.jpg'),
        ],
    },
    {
        'title': '2016 Toyota Prius, 82k miles',
        'category': ('Vehicles', 'Cars'),
        'price': '13900',
        'description': 'One owner, clean title, all service records. 50+ mpg. New 12V battery and brakes. Smog done.',
        'location': 'Willow Glen, San Jose', 'lat': 37.3041, 'lng': -121.8990,
        'tags': ['car', 'hybrid', 'toyota'],
        'photos': [
            photo('prius-1.jpg', '2015-2018 Toyota Prius S', 'TTTNIS', 'CC0',
                  COMMONS + '2015-2018_Toyota_Prius_S.jpg'),
            photo('prius-2.jpg', '2015-2018 Toyota Prius S rear', 'TTTNIS', 'CC0',
                  COMMONS + '2015-2018_Toyota_Prius_S_rear.jpg'),
            photo('prius-3.jpg', 'Toyota Prius (XW50) Washington DC Metro Area, USA (1)', 'OWS Photography',
                  'CC BY 4.0', COMMONS + 'Toyota_Prius_(XW50)_Washington_DC_Metro_Area,_USA_(1).jpg'),
        ],
    },
    {
        'title': 'Sunny 1BR near downtown Berkeley',
        'category': ('Housing', 'Apartments for Rent'),
        'price': '2650',
        'description': 'Top-floor one-bedroom, 5 min walk to BART. Hardwood floors, in-unit laundry, cats OK. '
                       'Available Dec 1.',
        'location': 'Downtown Berkeley', 'lat': 37.8716, 'lng': -122.2727,
        'tags': ['1br', 'apartment', 'berkeley'],
        'photos': [
            photo('apartment-1.jpg', 'Modern living room with stylish furniture and a view of the outdoors '
                  'in a cozy apartment setting', 'Shixart1985', 'CC BY 2.0',
                  COMMONS + 'Modern_living_room_with_stylish_furniture_and_a_view_of_the_outdoors_in_a_cozy_'
                            'apartment_setting.jpg'),
            photo('apartment-2.jpg', 'Living room in apartment of Condomínio do Edifício Zaher, Le Blond, '
                  'Rio de Janeiro, Brazil', 'Wilfredor', 'CC0',
                  COMMONS + 'Living_room_in_apartment_of_Condom%C3%ADnio_do_Edif%C3%ADcio_Zaher,_Le_Blond,_'
                            'Rio_de_Janeiro,_Brazil.jpg'),
            photo('apartment-3.jpg', 'The living room that needs houseplants', 'Lo (Flickr)', 'CC0',
                  COMMONS + 'The_living_room_that_needs_houseplants.jpg'),
        ],
    },
    {
        'title': 'Weekend barista at waterfront café',
        'category': ('Jobs', 'Part-time'),
        'price': None,
        'description': 'Saturday and Sunday mornings, $24/hr plus tips. Espresso experience preferred but we '
                       'will train the right person.',
        'location': 'Sausalito', 'lat': 37.8591, 'lng': -122.4853,
        'tags': ['barista', 'cafe', 'weekend'],
        'photos': [
            photo('barista-1.jpg', 'Girl Making Espresso', 'Petteri Sulonen', 'CC BY 2.0',
                  COMMONS + 'Girl_Making_Espresso.jpg'),
            photo('barista-2.jpg', 'A barista carefully tamping espresso grounds at a busy street-side coffee '
                  'stall', 'PattayaPatrol', 'CC BY-SA 4.0',
                  COMMONS + 'DSC_9564_A_barista_carefully_tamping_espresso_grounds_at_a_busy_street-side_'
                            'coffee_stall_preparing_fresh_coffee_for_customers.jpg'),
        ],
    },
    {
        'title': 'Piano lessons for all ages',
        'category': ('Services', 'Lessons & Tutoring'),
        'price': '60',
        'description': 'Conservatory-trained teacher, 15 years experience. Beginners welcome. 45-minute lessons '
                       'in my studio or your home.',
        'location': 'San Mateo', 'lat': 37.5630, 'lng': -122.3255,
        'tags': ['lessons', 'music', 'piano'],
        'photos': [
            photo('piano-1.jpg', 'Picture of piano lesson still under Covid-19 recovery time', 'Jason M. C., Han',
                  'CC BY-SA 4.0', COMMONS + 'Picture_of_piano_lesson_still_under_Covid-19_recovery_time.jpg'),
            photo('piano-2.jpg', 'Guna Goluba mūzika', 'LVinRU', 'CC BY-SA 4.0',
                  COMMONS + 'Guna_Goluba_m%C5%ABzika.jpg'),
        ],
    },
    {
        'title': 'Found: orange tabby cat near Central Park',
        'category': ('Community', 'Lost & Found'),
        'price': None,
        'description': 'Friendly orange tabby with a blue collar, no tag. Found by the lake on Sunday. '
                       'Describe markings to claim.',
        'location': 'Central Park, Fremont', 'lat': 37.5485, 'lng': -121.9886,
        'tags': ['cat', 'found pet'],
        'photos': [
            photo('cat-1.jpg', 'Orange tabby cat sitting on fallen leaves-Hisashi-01A', 'Hisashi', 'CC BY-SA 2.0',
                  COMMONS + 'Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01A.jpg'),
            photo('cat-2.jpg', 'Orange tabby cat sitting on fallen leaves-Hisashi-01', 'Hisashi', 'CC BY-SA 2.0',
                  COMMONS + 'Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01.jpg'),
        ],
    },
]


class Command(BaseCommand):
    help = ('Create demo ads around the SF Bay Area with real photos (safe to run repeatedly). '
            'They belong to a demo user; delete that user to remove them.')

    def add_arguments(self, parser):
        parser.add_argument('--user', default=DEMO_USERNAME,
                            help=f'Owner of the demo ads (created if missing, default "{DEMO_USERNAME}").')
        parser.add_argument('--fresh', action='store_true',
                            help="Delete that user's existing demo ads first, then recreate them.")

    @transaction.atomic
    def handle(self, *args, user, fresh, **options):
        call_command('seed_categories', stdout=self.stdout)  # the ads need these categories

        User = get_user_model()
        owner = User.objects.filter(username=user).first()
        if owner is not None and owner.has_usable_password():
            # Someone signed up with this name; don't attach demo ads to a real account.
            raise CommandError(f'"{user}" is a real account (it has a password); choose another --user.')
        if owner is None:
            owner = User(username=user)
            owner.set_unusable_password()  # a placeholder seller, not a real login
            owner.save()

        titles = [spec['title'] for spec in DEMO_ADS]
        if fresh:
            for ad in Ad.objects.filter(owner=owner, title__in=titles):
                ad.delete()  # cascades to images; the post_delete signal removes the files

        created = 0
        for spec in DEMO_ADS:
            if Ad.objects.filter(owner=owner, title=spec['title']).exists():
                continue
            parent_name, name = spec['category']
            ad = Ad.objects.create(
                owner=owner,
                title=spec['title'],
                description=spec['description'],
                price=Decimal(spec['price']) if spec['price'] is not None else None,
                category=Category.objects.get(parent__name=parent_name, name=name),
                location_name=spec['location'],
                latitude=spec['lat'],
                longitude=spec['lng'],
            )
            ad.tags.set([Tag.objects.get_or_create(name=t)[0] for t in spec['tags']])
            for p in spec['photos'][:AdImage.MAX_PER_AD]:
                with open(PHOTO_DIR / p['file'], 'rb') as fh:
                    AdImage.create_from_file(ad, fh)
            created += 1

        skipped = len(DEMO_ADS) - created
        self.stdout.write(self.style.SUCCESS(
            f'Seeded demo ads for "{owner.username}" ({created} new, {skipped} already there).'))
