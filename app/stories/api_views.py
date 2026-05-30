from django.db.models import Q, Count
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import Story, StoryBlock
from .serializers import StoryBlockSerializer, StoryListSerializer, StorySerializer


class IsAuthorOrFamilyRead(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        story = obj if isinstance(obj, Story) else obj.story
        if request.method in permissions.SAFE_METHODS:
            return story.visibility == 'family' or story.author == request.user
        return story.author == request.user


class StoryViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrFamilyRead]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Story.objects
            .select_related('author', 'author__profile')
            .filter(Q(visibility='family') | Q(author=user))
        )
        # 列表只需 block 数量,用 annotate;详情才加载 block 正文
        if self.action == 'list':
            qs = qs.annotate(_block_count=Count('blocks', distinct=True)).order_by('-date', '-id')
        else:
            qs = qs.prefetch_related('blocks')
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q))
        year = self.request.query_params.get('year')
        if year:
            qs = qs.filter(date__year=year)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return StoryListSerializer
        return StorySerializer

    @action(detail=True, methods=['post'], url_path='cover')
    def upload_cover(self, request, pk=None):
        story = self.get_object()
        if story.author != request.user:
            return Response({'detail': '只能改自己的故事'}, status=status.HTTP_403_FORBIDDEN)
        f = request.FILES.get('cover')
        if not f:
            return Response({'detail': '缺少 cover 文件'}, status=status.HTTP_400_BAD_REQUEST)
        story.cover = f
        story.cover_immich_asset_id = ''
        story.save(update_fields=['cover', 'cover_immich_asset_id', 'updated_at'])
        return Response(StorySerializer(story, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='blocks')
    def add_block(self, request, pk=None):
        """添加内容块。

        text 块：{ kind:'text', text:'...', order:0 }
        photo 块：multipart，字段 kind='photo' image=<file> caption=''
        immich 块：{ kind:'immich', immich_asset_id:'...', immich_filename:'...', caption:'', order:0 }
        """
        story = self.get_object()
        if story.author != request.user:
            return Response({'detail': '只能编辑自己的故事'}, status=status.HTTP_403_FORBIDDEN)

        kind = request.data.get('kind', 'text')
        if kind not in ('text', 'photo', 'immich'):
            return Response({'detail': 'kind 必须是 text/photo/immich'}, status=status.HTTP_400_BAD_REQUEST)

        # 自动排在最后
        last_order = story.blocks.order_by('-order').values_list('order', flat=True).first()
        default_order = (last_order or 0) + 1
        order = int(request.data.get('order', default_order))

        block = StoryBlock(story=story, kind=kind, order=order)

        if kind == 'text':
            block.text = request.data.get('text', '')
        elif kind == 'photo':
            f = request.FILES.get('image')
            if not f:
                return Response({'detail': '缺少 image 文件'}, status=status.HTTP_400_BAD_REQUEST)
            block.image = f
            block.caption = request.data.get('caption', '')
        elif kind == 'immich':
            aid = (request.data.get('immich_asset_id') or '').strip()
            if not aid:
                return Response({'detail': '缺少 immich_asset_id'}, status=status.HTTP_400_BAD_REQUEST)
            block.immich_asset_id = aid
            block.immich_filename = request.data.get('immich_filename', '')
            block.caption = request.data.get('caption', '')

        block.save()
        return Response(
            StoryBlockSerializer(block, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['patch'], url_path='blocks/(?P<block_id>[0-9]+)')
    def update_block(self, request, pk=None, block_id=None):
        """更新单个内容块（文字/说明/排序）。"""
        story = self.get_object()
        if story.author != request.user:
            return Response({'detail': '只能编辑自己的故事'}, status=status.HTTP_403_FORBIDDEN)
        try:
            block = story.blocks.get(pk=block_id)
        except StoryBlock.DoesNotExist:
            return Response({'detail': '内容块不存在'}, status=status.HTTP_404_NOT_FOUND)

        if 'text' in request.data:
            block.text = request.data['text']
        if 'caption' in request.data:
            block.caption = request.data['caption']
        if 'order' in request.data:
            block.order = int(request.data['order'])
        block.save()
        return Response(StoryBlockSerializer(block, context={'request': request}).data)

    @action(detail=True, methods=['delete'], url_path='blocks/(?P<block_id>[0-9]+)')
    def delete_block(self, request, pk=None, block_id=None):
        """删除单个内容块。"""
        story = self.get_object()
        if story.author != request.user:
            return Response({'detail': '只能编辑自己的故事'}, status=status.HTTP_403_FORBIDDEN)
        try:
            block = story.blocks.get(pk=block_id)
        except StoryBlock.DoesNotExist:
            return Response({'detail': '内容块不存在'}, status=status.HTTP_404_NOT_FOUND)
        block.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='reorder-blocks')
    def reorder_blocks(self, request, pk=None):
        """批量更新内容块排序。body: { orders: [{id, order}, ...] }"""
        story = self.get_object()
        if story.author != request.user:
            return Response({'detail': '只能编辑自己的故事'}, status=status.HTTP_403_FORBIDDEN)
        orders = request.data.get('orders', [])
        for item in orders:
            story.blocks.filter(pk=item['id']).update(order=item['order'])
        return Response({'ok': True})
