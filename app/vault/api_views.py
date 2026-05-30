from django.db import transaction
from django.db.models import Count, Q
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import Folder, File
from .serializers import FolderSerializer, FileSerializer

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB


class IsOwnerOrFamilyRead(permissions.BasePermission):
    """读:共享或自己;写:仅本人。"""
    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, 'owner', None) or getattr(obj, 'uploader', None)
        if request.method in permissions.SAFE_METHODS:
            return obj.visibility == 'family' or owner == request.user
        return owner == request.user


def _filter_visible(qs, user):
    return qs.filter(Q(visibility='family') | Q(owner=user) | Q(uploader=user))


class FolderViewSet(viewsets.ModelViewSet):
    serializer_class = FolderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrFamilyRead]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        shared = self.request.query_params.get('shared') == '1'
        base_filter = Q(visibility='family') if shared else Q(owner=user)
        qs = Folder.objects.select_related(
            'owner', 'parent', 'parent__parent', 'parent__parent__parent',
        ).annotate(
            file_count=Count('files', distinct=True),
            child_count=Count('children', distinct=True),
        ).filter(base_filter)
        parent = self.request.query_params.get('parent')
        if parent == 'null' or parent == '':
            qs = qs.filter(parent__isnull=True)
        elif parent:
            qs = qs.filter(parent_id=parent)
        return qs.order_by('name')


class FileViewSet(viewsets.ModelViewSet):
    serializer_class = FileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrFamilyRead]
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        shared = self.request.query_params.get('shared') == '1'
        base_filter = Q(visibility='family') if shared else Q(uploader=user)
        qs = File.objects.select_related('uploader', 'folder').filter(base_filter)
        # 全局搜索时不限文件夹
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
            return qs.order_by('-is_important', '-created_at')

        folder = self.request.query_params.get('folder')
        if folder == 'null' or folder == '':
            qs = qs.filter(folder__isnull=True)
        elif folder:
            qs = qs.filter(folder_id=folder)

        # 排序：name / size / created_at（默认重要性+时间）
        sort = self.request.query_params.get('sort', '')
        if sort == 'name':
            qs = qs.order_by('name')
        elif sort == 'size':
            qs = qs.order_by('-size_bytes')
        elif sort == 'date':
            qs = qs.order_by('-created_at')
        else:
            qs = qs.order_by('-is_important', '-created_at')
        return qs

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """批量上传:files=多个文件 + folder=可选 + is_important=可选"""
        files = request.FILES.getlist('files')
        if not files:
            return Response({'detail': '没有上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        # 文件大小校验（逐个检查，尽早返回）
        for f in files:
            if f.size > MAX_FILE_SIZE:
                return Response(
                    {'detail': f'「{f.name}」超过 200MB 单文件限制'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        folder_id = request.data.get('folder') or None
        folder = None
        if folder_id:
            try:
                folder = Folder.objects.get(pk=folder_id)
            except Folder.DoesNotExist:
                return Response({'detail': '文件夹不存在'}, status=status.HTTP_400_BAD_REQUEST)

        is_important = request.data.get('is_important') in ('true', 'True', '1', True)
        visibility = request.data.get('visibility') or 'family'
        if visibility not in ('family', 'private'):
            visibility = 'family'

        with transaction.atomic():
            created = [
                File.objects.create(
                    uploader=request.user,
                    folder=folder,
                    file=f,
                    name=f.name,
                    size_bytes=f.size,
                    mime_type=getattr(f, 'content_type', '') or '',
                    is_important=is_important,
                    visibility=visibility,
                )
                for f in files
            ]

        data = FileSerializer(created, many=True, context={'request': request}).data
        return Response({'created': data}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='move')
    def move(self, request, pk=None):
        """移动文件到其他文件夹。body: { folder_id: <id> | null }"""
        file = self.get_object()
        if file.uploader != request.user:
            return Response({'detail': '只能移动自己的文件'}, status=status.HTTP_403_FORBIDDEN)
        folder_id = request.data.get('folder_id')
        if folder_id is None:
            file.folder = None
        else:
            try:
                file.folder = Folder.objects.get(pk=folder_id)
            except Folder.DoesNotExist:
                return Response({'detail': '文件夹不存在'}, status=status.HTTP_404_NOT_FOUND)
        file.save(update_fields=['folder'])
        return Response(FileSerializer(file, context={'request': request}).data)
