from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Profile


def _is_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return user.profile.role == 'admin'
    except Profile.DoesNotExist:
        return False


class IsFamilyMember(BasePermission):
    """登录 + is_active=True。superuser 总是放行。"""
    message = '账号已被禁用或未登录'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_active)


class IsFamilyAdmin(BasePermission):
    """admin 或 superuser 才能执行。"""
    message = '需要家长权限'

    def has_permission(self, request, view):
        return _is_admin(request.user)


class IsFamilyAdminOrReadOnly(BasePermission):
    """读对所有登录家庭成员开放，写只允许 admin。"""
    message = '需要家长权限'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if request.method in SAFE_METHODS:
            return True
        return _is_admin(user)
