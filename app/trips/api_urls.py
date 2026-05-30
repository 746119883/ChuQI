from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register(r'trips', api_views.TripViewSet, basename='trip')
router.register(r'trip-items', api_views.TripItemViewSet, basename='trip-item')
router.register(r'trip-checklist', api_views.TripChecklistItemViewSet, basename='trip-checklist')

urlpatterns = [
    path('', include(router.urls)),
]
