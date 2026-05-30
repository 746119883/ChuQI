from rest_framework import permissions, viewsets

from .models import Note
from .serializers import NoteSerializer


class IsAuthorOrReadOnly(permissions.BasePermission):
    """登录用户都能看；只有作者能改/删。"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class NoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.select_related('author').all()
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        # 支持按作者过滤: ?author=1
        author_id = self.request.query_params.get('author')
        if author_id:
            qs = qs.filter(author_id=author_id)
        # 支持搜索: ?q=xxx
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(title__icontains=q)
        return qs
