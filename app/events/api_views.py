from datetime import date as date_cls, datetime, timedelta

from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from .models import Event
from .serializers import EventSerializer
from .utils import expand_for_range, expand_for_upcoming, gregorian_to_lunar_str


class IsOwnerOrFamilyRead(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.visibility == 'family' or obj.owner == request.user
        return obj.owner == request.user


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrFamilyRead]
    pagination_class = None  # 事件不分页,全量返回前端绘制

    def get_queryset(self):
        user = self.request.user
        return (
            Event.objects
            .select_related('owner')
            .filter(Q(visibility='family') | Q(owner=user))
            .order_by('date_month', 'date_day')
        )


def _parse_date(value, default):
    if not value:
        return default
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return default


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def occurrences(request):
    """指定时间范围内的所有事件 occurrence。?start=YYYY-MM-DD&end=YYYY-MM-DD"""
    user = request.user
    today = date_cls.today()
    start = _parse_date(request.query_params.get('start'), today)
    end = _parse_date(
        request.query_params.get('end'),
        today + timedelta(days=30),
    )
    if end < start:
        end = start

    events = Event.objects.select_related('owner').filter(
        Q(visibility='family') | Q(owner=user),
    )
    rows = expand_for_range(events, start, end)
    return Response(_serialize_rows(rows, request))


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def upcoming(request):
    """未来 N 天的事件。?days=30 默认 60。"""
    user = request.user
    try:
        days = int(request.query_params.get('days', 60))
    except ValueError:
        days = 60
    days = max(1, min(days, 365))

    events = Event.objects.select_related('owner').filter(
        Q(visibility='family') | Q(owner=user),
    )
    rows = expand_for_upcoming(events, days)
    return Response(_serialize_rows(rows, request))


def _serialize_rows(rows, request):
    return [
        {
            'date': d.isoformat(),
            'lunar_label': gregorian_to_lunar_str(d),
            'event': EventSerializer(ev, context={'request': request}).data,
        }
        for d, ev in rows
    ]
