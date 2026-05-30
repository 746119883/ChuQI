from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register(r'recipes', api_views.RecipeViewSet, basename='recipe')

urlpatterns = [
    path('', include(router.urls)),
]
