from django.urls import path

from . import views

app_name = 'messaging'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('<int:pk>/', views.conversation, name='conversation'),
    path('start/<int:ad_pk>/', views.start, name='start'),
]
