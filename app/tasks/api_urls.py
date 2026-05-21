from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'lists', api_views.TaskListViewSet, basename='tasklist')
router.register(r'tasks', api_views.TaskViewSet, basename='task')

urlpatterns = [
    path('', include(router.urls)),
]
