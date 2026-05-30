from datetime import date as date_cls
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import ExtractMonth
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import CATEGORY_CHOICES, LedgerEntry
from .serializers import LedgerEntrySerializer

CATEGORY_LABELS = dict(CATEGORY_CHOICES)


class IsRecorderOrFamilyRead(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.visibility == 'family' or obj.recorder == request.user
        return obj.recorder == request.user


class LedgerEntryViewSet(viewsets.ModelViewSet):
    serializer_class = LedgerEntrySerializer
    permission_classes = [permissions.IsAuthenticated, IsRecorderOrFamilyRead]

    def _base_qs(self):
        user = self.request.user
        return (
            LedgerEntry.objects
            .select_related('recorder')
            .filter(Q(visibility='family') | Q(recorder=user))
        )

    def get_queryset(self):
        qs = self._base_qs()
        params = self.request.query_params
        year = params.get('year')
        if year:
            qs = qs.filter(date__year=year)
        month = params.get('month')  # YYYY-MM
        if month and '-' in month:
            y, m = month.split('-')[:2]
            qs = qs.filter(date__year=y, date__month=m)
        entry_type = params.get('type')
        if entry_type in ('expense', 'income'):
            qs = qs.filter(entry_type=entry_type)
        category = params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """年度汇总：月度收支 + 支出分类占比。?year=YYYY (默认今年)"""
        try:
            year = int(request.query_params.get('year', date_cls.today().year))
        except ValueError:
            year = date_cls.today().year

        qs = self._base_qs().filter(date__year=year)

        # 月度收支
        monthly = {m: {'month': m, 'expense': Decimal('0'), 'income': Decimal('0')}
                   for m in range(1, 13)}
        rows = (
            qs.values('entry_type')
            .annotate(month=ExtractMonth('date'))
            .values('entry_type', 'month')
            .annotate(total=Sum('amount'))
        )
        for r in rows:
            bucket = monthly[r['month']]
            bucket['expense' if r['entry_type'] == 'expense' else 'income'] = r['total'] or Decimal('0')

        # 支出分类占比
        cat_rows = (
            qs.filter(entry_type='expense')
            .values('category')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        by_category = [
            {
                'category': c['category'],
                'category_display': CATEGORY_LABELS.get(c['category'], c['category']),
                'total': c['total'],
            }
            for c in cat_rows
        ]

        total_expense = sum((m['expense'] for m in monthly.values()), Decimal('0'))
        total_income = sum((m['income'] for m in monthly.values()), Decimal('0'))

        return Response({
            'year': year,
            'monthly': list(monthly.values()),
            'by_category': by_category,
            'total_expense': total_expense,
            'total_income': total_income,
        })

    @action(detail=False, methods=['get'])
    def years(self, request):
        """有数据的年份列表（年份选择器用）。"""
        ys = (
            self._base_qs()
            .dates('date', 'year', order='DESC')
        )
        return Response([d.year for d in ys])
