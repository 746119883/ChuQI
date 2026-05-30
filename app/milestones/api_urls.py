from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register(r'milestones', api_views.MilestoneViewSet, basename='milestone')

urlpatterns = [
    path('timeline/', api_views.timeline, name='timeline'),
    path('', include(router.urls)),
]
