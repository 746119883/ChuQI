from pathlib import Path

from django.db.models import Q
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import Folder, File
from .serializers import FolderSerializer, FileSerializer


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
        qs = Folder.objects.select_related('owner', 'parent').filter(
            Q(visibility='family') | Q(owner=user),
        )
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
        qs = File.objects.select_related('uploader', 'folder').filter(
            Q(visibility='family') | Q(uploader=user),
        )
        folder = self.request.query_params.get('folder')
        if folder == 'null' or folder == '':
            qs = qs.filter(folder__isnull=True)
        elif folder:
            qs = qs.filter(folder_id=folder)
        return qs.order_by('-is_important', '-created_at')

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """批量上传:files=多个文件 + folder=可选 + is_important=可选"""
        files = request.FILES.getlist('files')
        if not files:
            return Response(
                {'detail': '没有上传文件'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        folder_id = request.data.get('folder') or None
        folder = None
        if folder_id:
            try:
                folder = Folder.objects.get(pk=folder_id)
            except Folder.DoesNotExist:
                return Response(
                    {'detail': '文件夹不存在'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        is_important = request.data.get('is_important') in ('true', 'True', '1', True)
        visibility = request.data.get('visibility') or 'family'
        if visibility not in ('family', 'private'):
            visibility = 'family'

        created = []
        for f in files:
            obj = File.objects.create(
                uploader=request.user,
                folder=folder,
                file=f,
                name=f.name,
                size_bytes=f.size,
                mime_type=getattr(f, 'content_type', '') or '',
                is_important=is_important,
                visibility=visibility,
            )
            created.append(obj)

        data = FileSerializer(created, many=True, context={'request': request}).data
        return Response({'created': data}, status=status.HTTP_201_CREATED)
