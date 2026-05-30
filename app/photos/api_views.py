from itertools import chain

from django.db.models import F, Count
from django.db.models.functions import Coalesce
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import Album, Photo, Video
from .serializers import AlbumSerializer, PhotoSerializer, VideoSerializer
from .utils import (
    is_video_file,
    process_uploaded_photo,
    process_uploaded_video,
)


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner = getattr(obj, 'owner', None) or getattr(obj, 'uploader', None)
        return owner == request.user


class AlbumViewSet(viewsets.ModelViewSet):
    serializer_class = AlbumSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return Album.objects.select_related('owner', 'cover_photo').annotate(
            _photo_count=Count('photos', distinct=True),
            _video_count=Count('videos', distinct=True),
        )


class PhotoViewSet(viewsets.ModelViewSet):
    serializer_class = PhotoSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = (
            Photo.objects
            .select_related('uploader', 'album')
            .annotate(sort_date=Coalesce('taken_at', 'uploaded_at'))
            .order_by(F('sort_date').desc())
        )
        album_id = self.request.query_params.get('album')
        if album_id == 'null':
            qs = qs.filter(album__isnull=True)
        elif album_id:
            qs = qs.filter(album_id=album_id)
        return qs

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """统一上传:自动分流图片 / 视频。"""
        files = request.FILES.getlist('images') + request.FILES.getlist('files')
        if not files:
            return Response(
                {'detail': '没有上传文件'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        album_id = request.data.get('album') or None
        album = None
        if album_id:
            try:
                album = Album.objects.get(pk=album_id)
            except Album.DoesNotExist:
                return Response(
                    {'detail': '相册不存在'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        photos = []
        videos = []
        errors = []
        for f in files:
            try:
                if is_video_file(f.name):
                    v = Video.objects.create(
                        uploader=request.user,
                        album=album,
                        file=f,
                    )
                    process_uploaded_video(v)
                    videos.append(v)
                else:
                    p = Photo.objects.create(
                        uploader=request.user,
                        album=album,
                        image=f,
                    )
                    process_uploaded_photo(p, original_filename=f.name)
                    photos.append(p)
            except Exception as e:
                errors.append({'name': f.name, 'error': str(e)})

        ctx = {'request': request}
        return Response(
            {
                'photos': PhotoSerializer(photos, many=True, context=ctx).data,
                'videos': VideoSerializer(videos, many=True, context=ctx).data,
                'errors': errors,
            },
            status=status.HTTP_201_CREATED,
        )


class VideoViewSet(viewsets.ModelViewSet):
    serializer_class = VideoSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = (
            Video.objects
            .select_related('uploader', 'album')
            .annotate(sort_date=Coalesce('taken_at', 'uploaded_at'))
            .order_by(F('sort_date').desc())
        )
        album_id = self.request.query_params.get('album')
        if album_id == 'null':
            qs = qs.filter(album__isnull=True)
        elif album_id:
            qs = qs.filter(album_id=album_id)
        return qs


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def media_feed(request):
    """统一时间线:photos + videos 合并按时间倒序。"""
    album_id = request.query_params.get('album')

    photos_qs = Photo.objects.select_related('uploader', 'album')
    videos_qs = Video.objects.select_related('uploader', 'album')

    if album_id == 'null':
        photos_qs = photos_qs.filter(album__isnull=True)
        videos_qs = videos_qs.filter(album__isnull=True)
    elif album_id:
        photos_qs = photos_qs.filter(album_id=album_id)
        videos_qs = videos_qs.filter(album_id=album_id)

    photos_data = PhotoSerializer(photos_qs, many=True, context={'request': request}).data
    videos_data = VideoSerializer(videos_qs, many=True, context={'request': request}).data

    combined = list(chain(photos_data, videos_data))
    combined.sort(
        key=lambda x: x.get('taken_at') or x.get('uploaded_at') or '',
        reverse=True,
    )

    return Response({'results': combined, 'count': len(combined)})
