from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MAX_RADIUS_MILES, AdForm, SearchForm
from .models import Ad, Category, Tag, bounding_box, haversine_miles
from . import ratelimit
from .ratelimit import client_ip

PAGE_SIZE = 12
ADS_PER_USER_PER_DAY = 20
MAX_ADS_PER_USER = 200


def _nearest_page(ads, origin, radius, page_number):
    """A page of ads within `radius` miles of origin, nearest first.

    The database narrows candidates to a bounding box; exact distances are computed in
    Python on (id, lat, lng) rows only, so this works on any database. Full ads, with
    their tags and photos, are then loaded for the current page alone.
    """
    lat, lng = origin
    candidates = ads.exclude(latitude=None).exclude(longitude=None).filter(**bounding_box(lat, lng, radius))
    rows = []
    for pk, ad_lat, ad_lng in candidates.values_list('pk', 'latitude', 'longitude'):
        distance = haversine_miles(lat, lng, ad_lat, ad_lng)
        if distance <= radius:
            rows.append((distance, pk))
    rows.sort()
    page = Paginator(rows, PAGE_SIZE).get_page(page_number)
    by_pk = ads.in_bulk([pk for _, pk in page.object_list])
    page.object_list = [by_pk[pk] for _, pk in page.object_list]
    for ad, (distance, _) in zip(page.object_list, rows[page.start_index() - 1:]):
        ad.distance = distance
    return page


def _render_ad_list(request, ads, heading, extra=None):
    form = SearchForm(request.GET or None, client=client_ip(request))
    ads = ads.select_related('category__parent', 'owner').prefetch_related('tags', 'images')
    origin = None
    place_name = radius = None

    # Text and category filters apply even when another field (e.g. an unknown
    # location) is invalid, so a failed location lookup never widens the results.
    valid = form.is_valid()
    data = getattr(form, 'cleaned_data', {})
    q = data.get('q')
    if q:
        ads = ads.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(location_name__icontains=q))
    category = data.get('category')
    if category:
        ads = ads.filter(category_id__in=category.self_and_descendant_ids())
    if valid and data['lat'] is not None and data['lng'] is not None:
        origin = (data['lat'], data['lng'])
        place_name = data['place_name']
        radius = data['radius']

    if origin:
        page = _nearest_page(ads, origin, radius or MAX_RADIUS_MILES, request.GET.get('page'))
    else:
        page = Paginator(ads, PAGE_SIZE).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    context = {
        'page': page,
        'form': form,
        'heading': heading,
        'origin': origin,
        'place_name': place_name,
        'radius': radius,
        'querystring': query.urlencode(),
        'filtered': any(request.GET.get(k) for k in ('q', 'category', 'near'))
                    or bool(request.GET.get('lat') and request.GET.get('lng')),
        'max_radius': MAX_RADIUS_MILES,
        'top_categories': Category.objects.filter(parent=None),
    }
    context.update(extra or {})
    return render(request, 'ads/ad_list.html', context)


def ad_list(request):
    return _render_ad_list(request, Ad.objects.all(), 'Latest ads', {'is_home': True})


def category_ads(request, slug):
    category = get_object_or_404(Category, slug=slug)
    ads = Ad.objects.filter(category_id__in=category.self_and_descendant_ids())
    return _render_ad_list(request, ads, str(category), {'category': category})


def tag_ads(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    return _render_ad_list(request, tag.ads.all(), f'Tagged “{tag.name}”', {'tag': tag})


def category_list(request):
    categories = Category.objects.filter(parent=None).prefetch_related(
        Prefetch('subcategories', queryset=Category.objects.annotate(ad_count=Count('ads')))
    )
    tags = Tag.objects.annotate(ad_count=Count('ads')).filter(ad_count__gt=0).order_by('-ad_count', 'name')[:50]
    return render(request, 'ads/category_list.html', {'categories': categories, 'tags': tags})


def ad_detail(request, pk):
    ad = get_object_or_404(
        Ad.objects.select_related('category__parent', 'owner').prefetch_related('images', 'tags'), pk=pk
    )
    return render(request, 'ads/ad_detail.html', {'ad': ad})


def _posting_limit_error(user):
    if ratelimit.count('post-ad', user.pk, 60 * 60 * 24) >= ADS_PER_USER_PER_DAY:
        return f'You can post up to {ADS_PER_USER_PER_DAY} ads a day. Please try again tomorrow.'
    if user.ads.count() >= MAX_ADS_PER_USER:
        return f'You can have up to {MAX_ADS_PER_USER} ads. Delete some old ones to post more.'
    return None


@login_required
@transaction.atomic
def ad_create(request):
    form = AdForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        limit_error = _posting_limit_error(request.user)
        if limit_error:
            form.add_error(None, limit_error)
            return render(request, 'ads/ad_form.html', {'form': form}, status=429)
        ratelimit.hit('post-ad', request.user.pk, 60 * 60 * 24)
        ad = form.save(commit=False)
        ad.owner = request.user
        ad.save()
        form.save_related(ad)
        messages.success(request, 'Your ad has been posted.')
        return redirect(ad)
    return render(request, 'ads/ad_form.html', {'form': form})


@login_required
@transaction.atomic
def ad_edit(request, pk):
    ad = get_object_or_404(Ad, pk=pk, owner=request.user)
    saved_title = ad.title  # validation updates `ad` in place; the heading should not
    form = AdForm(request.POST or None, request.FILES or None, instance=ad)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your ad has been updated.')
        return redirect(ad)
    return render(request, 'ads/ad_form.html', {'form': form, 'ad': ad, 'saved_title': saved_title})


@login_required
def ad_delete(request, pk):
    ad = get_object_or_404(Ad, pk=pk)
    if ad.owner != request.user:
        raise Http404
    if request.method == 'POST':
        ad.delete()
        messages.success(request, f'“{ad.title}” was deleted.')
        return redirect('ads:my_ads')
    return render(request, 'ads/ad_confirm_delete.html', {'ad': ad})


@login_required
def my_ads(request):
    ads = request.user.ads.select_related('category__parent').prefetch_related('images')
    page = Paginator(ads, PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'ads/my_ads.html', {'page': page})
