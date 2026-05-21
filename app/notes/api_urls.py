from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import api_views

router = DefaultRouter()
router.register(r'notes', api_views.NoteViewSet, basename='note')

urlpatterns = [
    # 认证
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', api_views.register, name='register'),
    path('auth/me/', api_views.me, name='me'),

    # 业务资源
    path('', include(router.urls)),
]
