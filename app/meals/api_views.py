import random
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import _is_admin
from recipes.models import Recipe

from .models import DiningOption, MealLog
from .serializers import (
    DiningOptionSerializer,
    MealLogSerializer,
    RollResultSerializer,
    recipe_cover_url,
)


class IsOwnerOrFamilyRead(permissions.BasePermission):
    """家人都能读；只有创建者本人或家长能改/删。"""
    owner_attr = 'created_by'

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner = getattr(obj, self.owner_attr, None)
        return owner == request.user or _is_admin(request.user)


class DiningOptionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrFamilyRead]
    serializer_class = DiningOptionSerializer

    def get_queryset(self):
        qs = DiningOption.objects.select_related('created_by', 'created_by__profile')
        kind = self.request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        if self.request.query_params.get('active') in ('1', 'true'):
            qs = qs.filter(is_active=True)
        return qs


class MealLogViewSet(viewsets.ModelViewSet):
    serializer_class = MealLogSerializer

    def get_permissions(self):
        # MealLog 的属主字段是 recorder，复用同一权限类但换字段
        perm = IsOwnerOrFamilyRead()
        perm.owner_attr = 'recorder'
        return [perm]

    def get_queryset(self):
        qs = (
            MealLog.objects
            .select_related('recorder', 'recorder__profile', 'recipe', 'option')
        )
        meal_type = self.request.query_params.get('meal_type')
        if meal_type:
            qs = qs.filter(meal_type=meal_type)
        date_from = self.request.query_params.get('from')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        date_to = self.request.query_params.get('to')
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if self.request.query_params.get('mine') in ('1', 'true'):
            qs = qs.filter(recorder=self.request.user)
        return qs

    @action(detail=False, methods=['get'])
    def roll(self, request):
        """摇一摇：从菜谱 + 就餐选项里加权随机推荐。

        query params:
          source       all(默认) | recipe | option
          kind         仅就餐选项按方式过滤 (home/takeout/dineout)
          exclude_days 排除最近 N 天吃过的，默认 3，0=不排除
          count        返回候选总数(含主推)，默认 4
        返回 { main: <候选>, alternatives: [...] }，池为空时 main=null。
        """
        user = request.user
        source = request.query_params.get('source', 'all')
        kind = request.query_params.get('kind')
        try:
            exclude_days = max(0, int(request.query_params.get('exclude_days', 3)))
        except (TypeError, ValueError):
            exclude_days = 3
        try:
            count = max(1, min(int(request.query_params.get('count', 4)), 10))
        except (TypeError, ValueError):
            count = 4

        # 最近吃过的，用于排除（custom_name 无 id，无法排除）
        recent_recipe_ids, recent_option_ids = set(), set()
        if exclude_days > 0:
            since = timezone.localdate() - timedelta(days=exclude_days)
            recent = MealLog.objects.filter(date__gte=since)
            recent_recipe_ids = set(
                recent.exclude(recipe__isnull=True).values_list('recipe_id', flat=True)
            )
            recent_option_ids = set(
                recent.exclude(option__isnull=True).values_list('option_id', flat=True)
            )

        pool = []        # [(candidate_dict, weight)]

        if source in ('all', 'recipe') and not kind:
            recipes = (
                Recipe.objects
                .filter(Q(visibility='family') | Q(author=user))
                .exclude(id__in=recent_recipe_ids)
            )
            for r in recipes:
                pool.append((
                    {
                        'type': 'recipe',
                        'id': r.id,
                        'name': r.title,
                        'kind': None,
                        'kind_display': None,
                        'cover_url': recipe_cover_url(r, request),
                    },
                    1,
                ))

        if source in ('all', 'option'):
            options = DiningOption.objects.filter(is_active=True).exclude(
                id__in=recent_option_ids,
            )
            if kind:
                options = options.filter(kind=kind)
            for o in options:
                pool.append((
                    {
                        'type': 'option',
                        'id': o.id,
                        'name': o.name,
                        'kind': o.kind,
                        'kind_display': o.get_kind_display(),
                        'cover_url': None,
                    },
                    o.weight or 1,
                ))

        if not pool:
            return Response({'main': None, 'alternatives': [], 'pool_size': 0})

        # 加权无放回抽样：每次按权重抽一个，抽到的从池里移除
        picked = []
        candidates = list(pool)
        for _ in range(min(count, len(candidates))):
            weights = [w for _, w in candidates]
            chosen = random.choices(range(len(candidates)), weights=weights, k=1)[0]
            picked.append(candidates.pop(chosen)[0])

        return Response({
            'main': RollResultSerializer(picked[0]).data,
            'alternatives': RollResultSerializer(picked[1:], many=True).data,
            'pool_size': len(pool),
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """最近吃得最多的（按出现次数）。query: days 默认 30。"""
        try:
            days = max(1, int(request.query_params.get('days', 30)))
        except (TypeError, ValueError):
            days = 30
        since = timezone.localdate() - timedelta(days=days)
        logs = (
            MealLog.objects
            .filter(date__gte=since)
            .select_related('recipe', 'option')
        )
        counter = {}
        for log in logs:
            name = log.display_name
            if name == '(未填)':
                continue
            counter[name] = counter.get(name, 0) + 1
        top = sorted(counter.items(), key=lambda kv: -kv[1])[:10]
        return Response({
            'days': days,
            'total': logs.count(),
            'top': [{'name': n, 'count': c} for n, c in top],
        })
