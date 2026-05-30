from datetime import date as date_cls, datetime, timedelta

from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import Profile
from accounts.serializers import UserSerializer

from .models import Event
from .serializers import EventSerializer
from .utils import (
    expand_for_range,
    expand_for_upcoming,
    gregorian_to_lunar_str,
    profile_birthday_occurrences,
)

# 生日卡片默认颜色（粉）
BIRTHDAY_COLOR = '#ec4899'


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

    rows = _collect(user, start, end, request)
    return Response(rows)


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

    today = date_cls.today()
    rows = _collect(user, today, today + timedelta(days=days), request)
    return Response(rows)


def _collect(user, start, end, request):
    """汇总 [start, end] 内的真实 Event + 家庭成员资料生日，统一序列化、按日期升序。"""
    # 1) 真实事件
    events = Event.objects.select_related('owner').filter(
        Q(visibility='family') | Q(owner=user),
    )
    combined = []
    for d, ev in expand_for_range(events, start, end):
        combined.append((
            d,
            {
                'date': d.isoformat(),
                'lunar_label': gregorian_to_lunar_str(d),
                'event': EventSerializer(ev, context={'request': request}).data,
            },
        ))

    # 2) 家庭成员资料里的生日（自动生成，不可删/改，去本人资料里改）
    profiles = (
        Profile.objects
        .select_related('user')
        .filter(birthday__isnull=False, user__is_active=True)
    )
    for d, profile in profile_birthday_occurrences(profiles, start, end):
        combined.append((d, _serialize_profile_birthday(d, profile, request)))

    combined.sort(key=lambda r: r[0])
    return [payload for _, payload in combined]


def _serialize_profile_birthday(d, profile, request):
    u = profile.user
    display = profile.nickname or u.username
    return {
        'date': d.isoformat(),
        'lunar_label': gregorian_to_lunar_str(d),
        'event': {
            'id': f'profile-{u.id}',
            'owner': UserSerializer(u, context={'request': request}).data,
            'title': f'{display} 生日',
            'description': '',
            'event_type': 'birthday',
            'color': BIRTHDAY_COLOR,
            'visibility': 'family',
            'is_lunar': profile.birthday_is_lunar,
            'date_year': profile.birthday.year,
            'date_month': profile.birthday.month,
            'date_day': profile.birthday.day,
            'all_day': True,
            'start_time': None,
            'end_time': None,
            'yearly_recurring': True,
            'remind_days_before': None,
            'created_at': None,
            'updated_at': None,
            'is_profile_birthday': True,
        },
    }
