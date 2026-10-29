from django.core.management.base import BaseCommand

from ads.models import Category

CATEGORIES = {
    'For Sale': ['Electronics', 'Furniture', 'Clothing', 'Books', 'Sports & Outdoors'],
    'Vehicles': ['Cars', 'Motorcycles', 'Bicycles', 'Parts & Accessories'],
    'Housing': ['Apartments for Rent', 'Houses for Sale', 'Rooms & Shared', 'Commercial'],
    'Jobs': ['Full-time', 'Part-time', 'Freelance'],
    'Services': ['Home Repair', 'Lessons & Tutoring', 'Moving', 'Pet Care'],
    'Community': ['Events', 'Lost & Found', 'Volunteers'],
}


class Command(BaseCommand):
    help = 'Create a starter set of categories and subcategories (safe to run repeatedly).'

    def handle(self, *args, **options):
        created = 0
        for parent_name, children in CATEGORIES.items():
            parent, was_created = Category.objects.get_or_create(name=parent_name, parent=None)
            created += was_created
            for child_name in children:
                _, was_created = Category.objects.get_or_create(name=child_name, parent=parent)
                created += was_created
        self.stdout.write(self.style.SUCCESS(f'Seeded categories ({created} new).'))
