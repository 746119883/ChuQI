from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import api_views

router = DefaultRouter()
router.register(r'family/invitations', api_views.InvitationViewSet, basename='invitation')

urlpatterns = [
    # 认证
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', api_views.MeView.as_view(), name='me'),
    path('auth/register/', api_views.register_with_code, name='register'),

    # 邀请码查询（注册页用）
    path('family/invitations/lookup/<str:code>/', api_views.invitation_lookup, name='invitation_lookup'),

    # 家庭成员
    path('family/members/', api_views.MembersView.as_view(), name='members'),
    path('family/members/<int:user_id>/', api_views.MemberDetailView.as_view(), name='member_detail'),

    path('', include(router.urls)),
]
