from django.contrib import admin

from .models import Ad, Category, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'slug']
    list_filter = ['parent']
    prepopulated_fields = {'slug': ['name']}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'category', 'price', 'location_name', 'created_at']
    list_filter = ['category', 'tags']
    search_fields = ['title', 'description', 'location_name']
    filter_horizontal = ['tags']
