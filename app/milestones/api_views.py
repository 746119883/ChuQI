from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from immich.client import asset_url
from trips.models import Trip

from .models import Milestone
from .serializers import MilestoneSerializer


class IsCreatorOrReadOnly(permissions.BasePermission):
    """家人都能看；只有记录人能改/删。"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.created_by_id == request.user.id


class MilestoneViewSet(viewsets.ModelViewSet):
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.IsAuthenticated, IsCreatorOrReadOnly]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        return (
            Milestone.objects
            .select_related('created_by', 'created_by__profile')
            .filter(Q(visibility='family') | Q(created_by=user))
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='cover',
            parser_classes=[MultiPartParser, FormParser])
    def upload_cover(self, request, pk=None):
        milestone = self.get_object()
        if milestone.created_by_id != request.user.id:
            return Response({'detail': '只能改自己记录的大事'}, status=status.HTTP_403_FORBIDDEN)
        f = request.FILES.get('cover')
        if not f:
            return Response({'detail': '缺少 cover 文件'}, status=status.HTTP_400_BAD_REQUEST)
        milestone.cover = f
        milestone.cover_immich_asset_id = ''
        milestone.save(update_fields=['cover', 'cover_immich_asset_id', 'updated_at'])
        return Response(
            MilestoneSerializer(milestone, context={'request': request}).data
        )


def _abs(request, url):
    return request.build_absolute_uri(url) if (request and url) else url


@api_view(['GET'])
def timeline(request):
    """家庭时间轴：大事记 + 旅行，合并后按日期倒序。"""
    user = request.user
    entries = []

    milestones = (
        Milestone.objects
        .select_related('created_by', 'created_by__profile')
        .filter(Q(visibility='family') | Q(created_by=user))
    )
    for m in milestones:
        if m.cover_immich_asset_id:
            cover = _abs(request, asset_url(m.cover_immich_asset_id, 'preview'))
        elif m.cover:
            cover = _abs(request, m.cover.url)
        else:
            cover = None
        entries.append({
            'kind': 'milestone',
            'id': m.id,
            'date': m.date.isoformat(),
            'end_date': None,
            'title': m.title,
            'subtitle': m.get_milestone_type_display(),
            'milestone_type': m.milestone_type,
            'icon': m.icon,
            'cover_url': cover,
            'description': m.description,
        })

    trips = (
        Trip.objects
        .select_related('owner')
        .filter(Q(visibility='family') | Q(owner=user))
    )
    for t in trips:
        if t.cover_immich_asset_id:
            cover = _abs(request, asset_url(t.cover_immich_asset_id, 'preview'))
        elif t.cover:
            cover = _abs(request, t.cover.url)
        else:
            cover = None
        entries.append({
            'kind': 'trip',
            'id': t.id,
            'date': t.start_date.isoformat(),
            'end_date': t.end_date.isoformat() if t.end_date else None,
            'title': t.title,
            'subtitle': t.destination or '',
            'milestone_type': 'travel',
            'icon': '✈️',
            'cover_url': cover,
            'description': t.summary,
        })

    entries.sort(key=lambda e: e['date'], reverse=True)
    return Response(entries)
