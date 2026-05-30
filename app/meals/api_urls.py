from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register(r'dining-options', api_views.DiningOptionViewSet, basename='dining-option')
router.register(r'meal-logs', api_views.MealLogViewSet, basename='meal-log')

urlpatterns = [
    path('', include(router.urls)),
]
