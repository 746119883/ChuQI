from datetime import datetime, time, timedelta, timezone as dt_tz

from django.conf import settings
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from feed.models import Moment, MomentImage
from immich.client import ImmichClient, ImmichError

from .models import Trip, TripChecklistItem, TripItem
from .serializers import (
    TripChecklistItemSerializer,
    TripItemSerializer,
    TripListSerializer,
    TripSerializer,
)


class IsOwnerOrFamilyRead(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, 'owner', None) or getattr(getattr(obj, 'trip', None), 'owner', None)
        if request.method in permissions.SAFE_METHODS:
            visibility = getattr(obj, 'visibility', None) or getattr(getattr(obj, 'trip', None), 'visibility', 'family')
            return visibility == 'family' or owner == request.user
        return owner == request.user


class TripViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrFamilyRead]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Trip.objects
            .select_related('owner')
            .prefetch_related('items', 'checklist', 'checklist__created_by')
            .filter(Q(visibility='family') | Q(owner=user))
        )
        st = self.request.query_params.get('status')
        if st in ('planning', 'ongoing', 'done'):
            # status 是计算属性，这里 python 端过滤
            return [t for t in qs if t.status == st]
        return qs

    def get_serializer_class(self):
        return TripListSerializer if self.action == 'list' else TripSerializer

    def _iso_range(self, trip):
        start = datetime.combine(trip.start_date, time.min, tzinfo=dt_tz.utc)
        end_date = trip.end_date or trip.start_date
        end = datetime.combine(end_date, time.max, tzinfo=dt_tz.utc) + timedelta(seconds=1)
        return (
            start.isoformat().replace('+00:00', 'Z'),
            end.isoformat().replace('+00:00', 'Z'),
        )

    @action(detail=True, methods=['post'], url_path='cover')
    def upload_cover(self, request, pk=None):
        trip = self.get_object()
        if trip.owner != request.user:
            return Response({'detail': '只能改自己的旅行'}, status=status.HTTP_403_FORBIDDEN)
        f = request.FILES.get('cover')
        if not f:
            return Response({'detail': '缺少 cover 文件'}, status=status.HTTP_400_BAD_REQUEST)
        trip.cover = f
        trip.cover_immich_asset_id = ''
        trip.save(update_fields=['cover', 'cover_immich_asset_id', 'updated_at'])
        return Response(TripSerializer(trip, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='to-moment')
    def to_moment(self, request, pk=None):
        """一键发一条动态（文字 = 标题+备注），可选带几张行程期间的 Immich 照片。"""
        trip = self.get_object()
        if trip.owner != request.user:
            return Response({'detail': '只能操作自己的旅行'}, status=status.HTTP_403_FORBIDDEN)

        parts = [f'🧳 {trip.title}']
        if trip.destination:
            parts.append(f'📍 {trip.destination}')
        if trip.summary:
            parts.append(trip.summary)
        content = '\n'.join(parts)

        moment = Moment.objects.create(
            author=request.user,
            content=content,
            visibility=trip.visibility,
        )

        # 附带行程期间的 Immich 照片（最多 9 张）
        attached = 0
        if settings.IMMICH_ENABLED and request.data.get('with_photos', True):
            after, before = self._iso_range(trip)
            try:
                data = ImmichClient().search_metadata(
                    size=9, taken_after=after, taken_before=before,
                )
                for i, a in enumerate(data.get('assets', {}).get('items', [])):
                    MomentImage.objects.create(
                        moment=moment, immich_asset_id=a['id'], order=i,
                    )
                    attached += 1
            except ImmichError:
                pass

        return Response(
            {'moment_id': moment.id, 'photos_attached': attached},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='to-immich-album')
    def to_immich_album(self, request, pk=None):
        """把行程期间拍的照片归集成一个 Immich 相册。"""
        trip = self.get_object()
        if trip.owner != request.user:
            return Response({'detail': '只能操作自己的旅行'}, status=status.HTTP_403_FORBIDDEN)
        if not settings.IMMICH_ENABLED:
            return Response({'detail': 'Immich 未启用'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        after, before = self._iso_range(trip)
        client = ImmichClient()
        try:
            assets = client.search_all_in_range(taken_after=after, taken_before=before)
            asset_ids = [a['id'] for a in assets]
            if not asset_ids:
                return Response({'detail': '这段时间在 Immich 里没有照片'}, status=status.HTTP_400_BAD_REQUEST)
            album = client.create_album(
                name=trip.title,
                asset_ids=asset_ids,
                description=f'由初七旅行「{trip.title}」自动归集',
            )
        except ImmichError as e:
            return Response({'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        trip.immich_album_id = album.get('id', '')
        trip.save(update_fields=['immich_album_id', 'updated_at'])
        return Response({
            'album_id': album.get('id'),
            'album_name': album.get('albumName'),
            'asset_count': len(asset_ids),
        }, status=status.HTTP_201_CREATED)


class TripItemViewSet(viewsets.ModelViewSet):
    serializer_class = TripItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrFamilyRead]

    def get_queryset(self):
        user = self.request.user
        qs = TripItem.objects.select_related('trip', 'trip__owner').filter(
            Q(trip__visibility='family') | Q(trip__owner=user),
        )
        trip_id = self.request.query_params.get('trip')
        if trip_id:
            qs = qs.filter(trip_id=trip_id)
        return qs


class IsFamilyTripChecklistPerm(permissions.BasePermission):
    """清单是协作的：家人可见的旅行，任何家人都能勾/改/删；私密的只有 owner。"""
    def has_object_permission(self, request, view, obj):
        trip = obj.trip
        if request.method in permissions.SAFE_METHODS:
            return trip.visibility == 'family' or trip.owner == request.user
        if trip.visibility == 'family':
            return True
        return trip.owner == request.user


class TripChecklistItemViewSet(viewsets.ModelViewSet):
    serializer_class = TripChecklistItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsFamilyTripChecklistPerm]

    def get_queryset(self):
        user = self.request.user
        qs = TripChecklistItem.objects.select_related('trip', 'trip__owner', 'created_by').filter(
            Q(trip__visibility='family') | Q(trip__owner=user),
        )
        trip_id = self.request.query_params.get('trip')
        if trip_id:
            qs = qs.filter(trip_id=trip_id)
        kind = self.request.query_params.get('kind')
        if kind in ('bring', 'buy'):
            qs = qs.filter(kind=kind)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
