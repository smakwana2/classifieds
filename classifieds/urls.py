from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.templatetags.static import static as static_url
from django.urls import include, path

from .theme import set_theme


def favicon(request):
    return redirect(static_url('icons/favicon.ico'), permanent=True)


urlpatterns = [
    # Browsers ask for /favicon.ico on their own (e.g. for non-HTML pages).
    path('favicon.ico', favicon),
    path('theme/', set_theme, name='set_theme'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('messages/', include('messaging.urls')),
    path('', include('legal.urls')),
    path('', include('ads.urls')),
]

# Serve uploaded images during development; use the web server for this in production.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
