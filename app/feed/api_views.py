from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import Moment, Reaction, Comment
from .serializers import MomentSerializer, CommentSerializer


class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class MomentViewSet(viewsets.ModelViewSet):
    serializer_class = MomentSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        # 家人可见的 + 自己发的私密
        return (
            Moment.objects
            .select_related('author')
            .prefetch_related('images', 'reactions', 'comments')
            .filter(Q(visibility='family') | Q(author=user))
        )

    @action(detail=True, methods=['post'], url_path='like')
    def toggle_like(self, request, pk=None):
        moment = self.get_object()
        reaction, created = Reaction.objects.get_or_create(
            moment=moment, user=request.user,
        )
        liked = True
        if not created:
            reaction.delete()
            liked = False
        # 不能用 moment.reactions.count():prefetch_related 缓存比这次操作更早
        count = Reaction.objects.filter(moment_id=moment.id).count()
        return Response({'liked': liked, 'count': count})

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        moment = self.get_object()
        if request.method == 'GET':
            qs = moment.comments.select_related('author').all()
            return Response(CommentSerializer(qs, many=True).data)
        # POST 新增评论
        serializer = CommentSerializer(
            data=request.data,
            context={'request': request, 'moment_id': moment.id},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CommentDetailViewSet(viewsets.GenericViewSet):
    """删除评论用 (只允许作者删除自己的评论)"""
    queryset = Comment.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, pk=None):
        comment = get_object_or_404(Comment, pk=pk)
        if comment.author != request.user:
            return Response(
                {'detail': '只能删除自己的评论'},
                status=status.HTTP_403_FORBIDDEN,
            )
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
