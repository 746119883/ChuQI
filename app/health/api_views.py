from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFamilyMember
from rest_framework.parsers import FormParser, MultiPartParser
from .models import (
    ALLOWED_ATTACHMENT_TYPES,
    CHILD_CHECKUP_SCHEDULE,
    CHILD_VACCINE_SCHEDULE,
    MAX_HEALTH_FILE_SIZE,
    CheckupPlan,
    CheckupResult,
    HealthAttachment,
    HealthProfile,
    HealthReminderSettings,
    MedicalVisit,
    VaccinePlan,
    VaccinationRecord,
    add_months,
    age_in_years,
)
from .serializers import (
    CheckupPlanSerializer,
    CheckupResultSerializer,
    HealthAttachmentSerializer,
    HealthProfileSerializer,
    HealthReminderSettingsSerializer,
    MedicalVisitSerializer,
    MemberHealthProfileSerializer,
    VaccinePlanSerializer,
    VaccinationRecordSerializer,
)


class HealthProfileListView(APIView):
    """GET /api/health/profiles/ — 所有活跃家庭成员及其健康档案。"""
    permission_classes = [IsFamilyMember]

    def get(self, request):
        members = (
            User.objects
            .filter(is_active=True)
            .select_related('profile', 'health_profile')
            .order_by('id')
        )
        data = MemberHealthProfileSerializer(
            members, many=True, context={'request': request}
        ).data
        return Response(data)


class HealthProfileDetailView(APIView):
    """GET /PATCH /api/health/profiles/{user_id}/ — 单成员健康档案。"""
    permission_classes = [IsFamilyMember]

    def _get_or_create(self, user_id):
        user = get_object_or_404(User, pk=user_id, is_active=True)
        profile, _ = HealthProfile.objects.get_or_create(user=user)
        return profile

    def get(self, request, user_id):
        profile = self._get_or_create(user_id)
        return Response(HealthProfileSerializer(profile).data)

    def patch(self, request, user_id):
        profile = self._get_or_create(user_id)
        serializer = HealthProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CheckupPlanViewSet(viewsets.ModelViewSet):
    """体检计划 CRUD。?user_id= 过滤某成员；家庭成员均可读写。"""
    permission_classes = [IsFamilyMember]
    serializer_class = CheckupPlanSerializer
    pagination_class = None  # 按成员的有界列表，不分页

    def get_queryset(self):
        qs = CheckupPlan.objects.all()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs

    @staticmethod
    def _spawn_next_if_recurring(plan):
        """周期性计划首次完成时，生成下一期 pending 条目。"""
        nxt = plan.next_date()
        if nxt:
            CheckupPlan.objects.create(
                user=plan.user,
                name=plan.name,
                scheduled_date=nxt,
                frequency=plan.frequency,
                interval_months=plan.interval_months,
                status='pending',
            )

    def perform_update(self, serializer):
        old_status = serializer.instance.status
        plan = serializer.save()
        if old_status != 'done' and plan.status == 'done':
            self._spawn_next_if_recurring(plan)

    @action(detail=False, methods=['post'], url_path='load-child-schedule')
    def load_child_schedule(self, request):
        """为 <7 岁儿童按出生日期生成国标体检时间表，仅追加缺失条目。"""
        user_id = request.data.get('user_id')
        user = get_object_or_404(User, pk=user_id, is_active=True)
        try:
            birthday = user.profile.birthday
        except Exception:
            birthday = None
        if not birthday:
            return Response({'detail': '该成员未填写出生日期'}, status=status.HTTP_400_BAD_REQUEST)
        age = age_in_years(birthday)
        if age is None or age >= 7:
            return Response({'detail': '国标体检时间表仅适用于 7 岁以下儿童'}, status=status.HTTP_400_BAD_REQUEST)

        existing_names = set(
            CheckupPlan.objects.filter(user=user).values_list('name', flat=True)
        )
        created = 0
        for name, months in CHILD_CHECKUP_SCHEDULE:
            if name in existing_names:
                continue
            CheckupPlan.objects.create(
                user=user,
                name=name,
                scheduled_date=add_months(birthday, months),
                frequency='once',
                status='pending',
            )
            created += 1
        return Response({
            'created': created,
            'skipped': len(CHILD_CHECKUP_SCHEDULE) - created,
        })

    @action(detail=True, methods=['get', 'put'], url_path='result')
    def result(self, request, pk=None):
        """GET 取结果；PUT 录入/更新结果并将计划置为已完成。"""
        plan = self.get_object()
        if request.method == 'GET':
            result = getattr(plan, 'result', None)
            if not result:
                return Response({'detail': '尚无结果'}, status=status.HTTP_404_NOT_FOUND)
            return Response(CheckupResultSerializer(result).data)

        result = getattr(plan, 'result', None)
        serializer = CheckupResultSerializer(result, data=request.data, partial=bool(result))
        serializer.is_valid(raise_exception=True)
        serializer.save(plan=plan)
        # 录入结果 → 计划自动完成（首次完成时周期性计划生成下一期）
        if plan.status != 'done':
            plan.status = 'done'
            plan.save(update_fields=['status'])
            self._spawn_next_if_recurring(plan)
        return Response(serializer.data)


class MetricsHistoryView(APIView):
    """GET /api/health/metrics-history/?user_id=&name= — 某成员某指标的历史。"""
    permission_classes = [IsFamilyMember]

    def get(self, request):
        user_id = request.query_params.get('user_id')
        name = request.query_params.get('name')
        if not user_id or not name:
            return Response({'detail': '需提供 user_id 和 name'}, status=status.HTTP_400_BAD_REQUEST)
        results = (
            CheckupResult.objects
            .filter(plan__user_id=user_id)
            .order_by('visit_date')
        )
        history = []
        for r in results:
            for m in (r.metrics or []):
                if m.get('name') == name:
                    history.append({
                        'date': r.visit_date.isoformat(),
                        'value': m.get('value'),
                        'unit': m.get('unit', ''),
                        'reference': m.get('reference', ''),
                        'abnormal': bool(m.get('abnormal')),
                    })
        return Response(history)


class HealthAttachmentViewSet(viewsets.ModelViewSet):
    """健康附件上传/列表/删除。?checkup_result= 过滤。"""
    permission_classes = [IsFamilyMember]
    serializer_class = HealthAttachmentSerializer
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    def get_queryset(self):
        qs = HealthAttachment.objects.all()
        cr = self.request.query_params.get('checkup_result')
        if cr:
            qs = qs.filter(checkup_result_id=cr)
        vr = self.request.query_params.get('vaccination_record')
        if vr:
            qs = qs.filter(vaccination_record_id=vr)
        mv = self.request.query_params.get('medical_visit')
        if mv:
            qs = qs.filter(medical_visit_id=mv)
        return qs

    def create(self, request, *args, **kwargs):
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': '缺少 file'}, status=status.HTTP_400_BAD_REQUEST)
        if f.size > MAX_HEALTH_FILE_SIZE:
            return Response({'detail': f'「{f.name}」超过 20MB 限制'}, status=status.HTTP_400_BAD_REQUEST)
        if f.content_type not in ALLOWED_ATTACHMENT_TYPES:
            return Response({'detail': '仅支持 JPEG/PNG/PDF'}, status=status.HTTP_400_BAD_REQUEST)
        attachment = HealthAttachment(
            file=f,
            name=f.name,
            size_bytes=f.size,
            content_type=f.content_type,
            uploaded_by=request.user,
        )
        cr = request.data.get('checkup_result')
        if cr:
            attachment.checkup_result = get_object_or_404(CheckupResult, pk=cr)
        vr = request.data.get('vaccination_record')
        if vr:
            attachment.vaccination_record = get_object_or_404(VaccinationRecord, pk=vr)
        mv = request.data.get('medical_visit')
        if mv:
            attachment.medical_visit = get_object_or_404(MedicalVisit, pk=mv)
        attachment.save()
        return Response(
            HealthAttachmentSerializer(attachment, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class VaccinePlanViewSet(viewsets.ModelViewSet):
    """疫苗计划 CRUD + 状态总览。?user_id= 过滤。"""
    permission_classes = [IsFamilyMember]
    serializer_class = VaccinePlanSerializer
    pagination_class = None

    def get_queryset(self):
        qs = VaccinePlan.objects.all()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs

    @action(detail=False, methods=['post'], url_path='load-child-schedule')
    def load_child_schedule(self, request):
        """按出生日期生成国家免疫规划时间表，仅追加缺失剂次。"""
        user_id = request.data.get('user_id')
        user = get_object_or_404(User, pk=user_id, is_active=True)
        try:
            birthday = user.profile.birthday
        except Exception:
            birthday = None
        if not birthday:
            return Response({'detail': '该成员未填写出生日期'}, status=status.HTTP_400_BAD_REQUEST)
        age = age_in_years(birthday)
        if age is None or age >= 7:
            return Response({'detail': '国家免疫规划时间表仅适用于 7 岁以下儿童'}, status=status.HTTP_400_BAD_REQUEST)

        existing = set(
            VaccinePlan.objects.filter(user=user)
            .values_list('vaccine_name', 'dose_number')
        )
        created = 0
        for name, dose, months in CHILD_VACCINE_SCHEDULE:
            if (name, dose) in existing:
                continue
            VaccinePlan.objects.create(
                user=user, vaccine_name=name, dose_number=dose,
                scheduled_date=add_months(birthday, months), status='pending',
            )
            created += 1
        return Response({
            'created': created,
            'skipped': len(CHILD_VACCINE_SCHEDULE) - created,
        })

    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request):
        """按 待接种/已接种/逾期 分组。?user_id= 必填。"""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': '需提供 user_id'}, status=status.HTTP_400_BAD_REQUEST)
        from datetime import date as _date
        today = _date.today()
        pending, done, overdue = [], [], []
        for p in VaccinePlan.objects.filter(user_id=user_id):
            data = VaccinePlanSerializer(p).data
            if p.status == 'done':
                done.append(data)
            elif p.status == 'pending' and p.scheduled_date < today:
                overdue.append(data)
            elif p.status == 'pending':
                pending.append(data)
        return Response({'pending': pending, 'done': done, 'overdue': overdue})

    @action(detail=True, methods=['get', 'put'], url_path='record')
    def record(self, request, pk=None):
        """GET 取接种记录；PUT 录入/更新并将计划置为已接种。"""
        plan = self.get_object()
        if request.method == 'GET':
            rec = getattr(plan, 'record', None)
            if not rec:
                return Response({'detail': '尚无记录'}, status=status.HTTP_404_NOT_FOUND)
            return Response(VaccinationRecordSerializer(rec).data)

        rec = getattr(plan, 'record', None)
        serializer = VaccinationRecordSerializer(rec, data=request.data, partial=bool(rec))
        serializer.is_valid(raise_exception=True)
        serializer.save(plan=plan)
        if plan.status != 'done':
            plan.status = 'done'
            plan.save(update_fields=['status'])
        return Response(serializer.data)


class HealthReminderSettingsView(APIView):
    """GET/PUT /api/health/reminder-settings/ — 家庭级提醒设置（单例）。"""
    permission_classes = [IsFamilyMember]

    def get(self, request):
        settings_obj = HealthReminderSettings.load()
        return Response(HealthReminderSettingsSerializer(settings_obj).data)

    def put(self, request):
        settings_obj = HealthReminderSettings.load()
        serializer = HealthReminderSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MedicalVisitViewSet(viewsets.ModelViewSet):
    """就医记录 CRUD。?user_id= 过滤，时间倒序。"""
    permission_classes = [IsFamilyMember]
    serializer_class = MedicalVisitSerializer
    pagination_class = None

    def get_queryset(self):
        qs = MedicalVisit.objects.all()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs
