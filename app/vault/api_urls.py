from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'vault/folders', api_views.FolderViewSet, basename='vault-folder')
router.register(r'vault/files', api_views.FileViewSet, basename='vault-file')

urlpatterns = [
    path('', include(router.urls)),
]
