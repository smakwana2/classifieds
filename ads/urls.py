from django.urls import path

from . import views

app_name = 'ads'

urlpatterns = [
    path('', views.ad_list, name='list'),
    path('ads/new/', views.ad_create, name='create'),
    path('ads/mine/', views.my_ads, name='my_ads'),
    path('ads/<int:pk>/', views.ad_detail, name='detail'),
    path('ads/<int:pk>/edit/', views.ad_edit, name='edit'),
    path('ads/<int:pk>/delete/', views.ad_delete, name='delete'),
    path('categories/', views.category_list, name='categories'),
    path('categories/<slug:slug>/', views.category_ads, name='category'),
    path('tags/<slug:slug>/', views.tag_ads, name='tag'),
]
