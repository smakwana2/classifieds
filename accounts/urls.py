from django.urls import include, path

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('delete/', views.delete_account, name='delete_account'),
    path('', include('django.contrib.auth.urls')),
]
