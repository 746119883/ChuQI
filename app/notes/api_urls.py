from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register(r'notes', api_views.NoteViewSet, basename='note')

urlpatterns = [
    path('', include(router.urls)),
]
