from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'moments', api_views.MomentViewSet, basename='moment')

urlpatterns = [
    path('feed/on-this-day/', api_views.on_this_day, name='on-this-day'),
    path('', include(router.urls)),
    path(
        'comments/<int:pk>/',
        api_views.CommentDetailViewSet.as_view({'delete': 'destroy'}),
        name='comment-detail',
    ),
]
