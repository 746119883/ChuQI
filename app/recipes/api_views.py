from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from tasks.models import Task, TaskList

from .models import Recipe
from .serializers import RecipeListSerializer, RecipeSerializer


class IsAuthorOrFamilyRead(permissions.BasePermission):
    """家人可见的可读；只有作者能改/删。"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.visibility == 'family' or obj.author == request.user
        return obj.author == request.user


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrFamilyRead]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Recipe.objects
            .select_related('author')
            .filter(Q(visibility='family') | Q(author=user))
        )
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        tag = self.request.query_params.get('tag')
        if tag:
            qs = qs.filter(tags__contains=[tag])
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        mine = self.request.query_params.get('mine')
        if mine in ('1', 'true'):
            qs = qs.filter(author=user)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return RecipeListSerializer
        return RecipeSerializer

    @action(detail=True, methods=['post'], url_path='cover')
    def upload_cover(self, request, pk=None):
        """本地上传封面（multipart, 字段名 cover）。"""
        recipe = self.get_object()
        if recipe.author != request.user:
            return Response({'detail': '只能改自己的菜谱'}, status=status.HTTP_403_FORBIDDEN)
        f = request.FILES.get('cover')
        if not f:
            return Response({'detail': '缺少 cover 文件'}, status=status.HTTP_400_BAD_REQUEST)
        recipe.cover = f
        recipe.cover_immich_asset_id = ''  # 本地封面覆盖 Immich 封面
        recipe.save(update_fields=['cover', 'cover_immich_asset_id', 'updated_at'])
        return Response(RecipeSerializer(recipe, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='to-shopping-list')
    def to_shopping_list(self, request, pk=None):
        """把食材一键加入购物清单。

        body 可选 { "list_id": <已有清单id> }，否则新建一个"买菜: <菜名>"清单。
        """
        recipe = self.get_object()
        ingredients = recipe.ingredients or []
        if not ingredients:
            return Response({'detail': '这个菜谱还没有食材'}, status=status.HTTP_400_BAD_REQUEST)

        list_id = request.data.get('list_id')
        if list_id:
            try:
                task_list = TaskList.objects.get(pk=list_id)
            except TaskList.DoesNotExist:
                return Response({'detail': '清单不存在'}, status=status.HTTP_404_NOT_FOUND)
            # 只能往自己的或共享清单加
            if task_list.owner != request.user and not task_list.is_shared:
                return Response({'detail': '无权操作该清单'}, status=status.HTTP_403_FORBIDDEN)
        else:
            task_list = TaskList.objects.create(
                owner=request.user,
                name=f'买菜: {recipe.title}',
                description=f'来自菜谱「{recipe.title}」',
                is_shared=True,
            )

        created = 0
        for ing in ingredients:
            name = (ing.get('name') or '').strip()
            if not name:
                continue
            amount = (ing.get('amount') or '').strip()
            title = f'{name} {amount}'.strip()
            Task.objects.create(list=task_list, title=title, created_by=request.user)
            created += 1

        return Response(
            {'list_id': task_list.id, 'list_name': task_list.name, 'added': created},
            status=status.HTTP_201_CREATED,
        )
