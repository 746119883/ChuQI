from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register(r'notifications', api_views.NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]
