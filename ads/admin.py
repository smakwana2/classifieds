from django.contrib import admin

from .models import Ad, AdImage, Category, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'slug']
    list_filter = ['parent']
    exclude = ['slug']  # generated on save, including the parent's name for subcategories


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    exclude = ['slug']  # generated on save, unique even when names slugify alike


class AdImageInline(admin.TabularInline):
    model = AdImage
    extra = 0
    max_num = AdImage.MAX_PER_AD


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    inlines = [AdImageInline]
    list_display = ['title', 'owner', 'category', 'price', 'location_name', 'created_at']
    list_filter = ['category', 'tags']
    search_fields = ['title', 'description', 'location_name']
    filter_horizontal = ['tags']
