from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register(r'stories', api_views.StoryViewSet, basename='story')

urlpatterns = [
    path('', include(router.urls)),
]
