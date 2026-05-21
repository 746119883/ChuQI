from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    path('', views.note_list, name='list'),
    path('<int:pk>/', views.note_detail, name='detail'),
]
