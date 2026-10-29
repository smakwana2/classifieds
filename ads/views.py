from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AdForm, SearchForm
from .models import Ad, Category, Tag

PAGE_SIZE = 12


def _render_ad_list(request, ads, heading, extra=None):
    form = SearchForm(request.GET or None)
    ads = ads.select_related('category__parent', 'owner').prefetch_related('tags', 'images')
    origin = None

    if form.is_valid():
        q = form.cleaned_data['q']
        if q:
            ads = ads.filter(
                Q(title__icontains=q) | Q(description__icontains=q) | Q(location_name__icontains=q)
            )
        category = form.cleaned_data['category']
        if category:
            ads = ads.filter(category_id__in=category.self_and_descendant_ids())
        lat, lng, radius = (form.cleaned_data[k] for k in ('lat', 'lng', 'radius'))
        if lat is not None and lng is not None:
            origin = (lat, lng)

    if origin:
        # Distance filtering is done in Python so this works on any database.
        results = []
        for ad in ads.exclude(latitude=None).exclude(longitude=None):
            ad.distance = ad.distance_km(*origin)
            if not radius or ad.distance <= radius:
                results.append(ad)
        results.sort(key=lambda a: a.distance)
        ads = results

    page = Paginator(ads, PAGE_SIZE).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    context = {
        'page': page,
        'form': form,
        'heading': heading,
        'origin': origin,
        'querystring': query.urlencode(),
    }
    context.update(extra or {})
    return render(request, 'ads/ad_list.html', context)


def ad_list(request):
    return _render_ad_list(request, Ad.objects.all(), 'Latest ads')


def category_ads(request, slug):
    category = get_object_or_404(Category, slug=slug)
    ads = Ad.objects.filter(category_id__in=category.self_and_descendant_ids())
    return _render_ad_list(request, ads, str(category), {'category': category})


def tag_ads(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    return _render_ad_list(request, tag.ads.all(), f'Tagged “{tag.name}”', {'tag': tag})


def category_list(request):
    categories = (
        Category.objects.filter(parent=None)
        .prefetch_related('subcategories')
    )
    tags = Tag.objects.annotate(ad_count=Count('ads')).filter(ad_count__gt=0).order_by('-ad_count', 'name')[:50]
    return render(request, 'ads/category_list.html', {'categories': categories, 'tags': tags})


def ad_detail(request, pk):
    ad = get_object_or_404(
        Ad.objects.select_related('category__parent', 'owner').prefetch_related('images', 'tags'), pk=pk
    )
    return render(request, 'ads/ad_detail.html', {'ad': ad})


@login_required
def ad_create(request):
    form = AdForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        ad = form.save(commit=False)
        ad.owner = request.user
        ad.save()
        form.save_related(ad)
        messages.success(request, 'Your ad has been posted.')
        return redirect(ad)
    return render(request, 'ads/ad_form.html', {'form': form})


@login_required
def ad_edit(request, pk):
    ad = get_object_or_404(Ad, pk=pk, owner=request.user)
    form = AdForm(request.POST or None, request.FILES or None, instance=ad)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your ad has been updated.')
        return redirect(ad)
    return render(request, 'ads/ad_form.html', {'form': form, 'ad': ad})


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
    ads = request.user.ads.select_related('category__parent')
    return render(request, 'ads/my_ads.html', {'ads': ads})
