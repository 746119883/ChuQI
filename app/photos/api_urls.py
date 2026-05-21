from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'albums', api_views.AlbumViewSet, basename='album')
router.register(r'photos', api_views.PhotoViewSet, basename='photo')
router.register(r'videos', api_views.VideoViewSet, basename='video')

urlpatterns = [
    path('media/', api_views.media_feed, name='media-feed'),
    path('', include(router.urls)),
]
