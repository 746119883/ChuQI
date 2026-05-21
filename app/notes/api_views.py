from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User

from .models import Note
from .serializers import NoteSerializer, UserSerializer


class IsAuthorOrReadOnly(permissions.BasePermission):
    """登录用户都能看；只有作者能改/删。"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class NoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.select_related('author').all()
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]

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


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """简易注册接口：用户名 + 密码"""
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    if not username or not password:
        return Response(
            {'detail': '用户名和密码必填'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(password) < 6:
        return Response(
            {'detail': '密码至少 6 位'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if User.objects.filter(username=username).exists():
        return Response(
            {'detail': '用户名已存在'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.create_user(username=username, password=password)
    return Response(
        UserSerializer(user).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
def me(request):
    """获取当前登录用户信息"""
    return Response(UserSerializer(request.user).data)
