from django.contrib import admin

from .models import TermsAcceptance


@admin.register(TermsAcceptance)
class TermsAcceptanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'version', 'accepted_at']
    readonly_fields = ['user', 'version', 'accepted_at']
    search_fields = ['user__username']
