from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'events', api_views.EventViewSet, basename='event')

urlpatterns = [
    path('events/occurrences/', api_views.occurrences, name='event-occurrences'),
    path('events/upcoming/', api_views.upcoming, name='event-upcoming'),
    path('', include(router.urls)),
]
