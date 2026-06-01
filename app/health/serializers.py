from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (
    CheckupPlan,
    CheckupResult,
    HealthAttachment,
    HealthProfile,
    HealthReminderSettings,
    MedicalVisit,
    VaccinePlan,
    VaccinationRecord,
)


ALLERGY_TYPES = {'drug', 'food', 'environment'}


class AllergyField(serializers.JSONField):
    """校验过敏史为 [{name, type, note}] 列表。"""
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if not isinstance(data, list):
            raise serializers.ValidationError('过敏史必须是列表')
        out = []
        for item in data:
            if not isinstance(item, dict):
                raise serializers.ValidationError('每条过敏记录必须是对象')
            name = (item.get('name') or '').strip()
            if not name:
                continue
            atype = (item.get('type') or '').strip()
            if atype and atype not in ALLERGY_TYPES:
                raise serializers.ValidationError(f'过敏类型非法：{atype}')
            out.append({
                'name': name,
                'type': atype,
                'note': (item.get('note') or '').strip(),
            })
        return out


class ChronicConditionField(serializers.JSONField):
    """校验慢性病为 [{name, diagnosed_date, note}] 列表。"""
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if not isinstance(data, list):
            raise serializers.ValidationError('慢性病必须是列表')
        out = []
        for item in data:
            if not isinstance(item, dict):
                raise serializers.ValidationError('每条慢性病记录必须是对象')
            name = (item.get('name') or '').strip()
            if not name:
                continue
            out.append({
                'name': name,
                'diagnosed_date': (item.get('diagnosed_date') or '').strip(),
                'note': (item.get('note') or '').strip(),
            })
        return out


class MedicationField(serializers.JSONField):
    """校验长期用药为 [{name, dosage, note}] 列表。"""
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if not isinstance(data, list):
            raise serializers.ValidationError('长期用药必须是列表')
        out = []
        for item in data:
            if not isinstance(item, dict):
                raise serializers.ValidationError('每条用药记录必须是对象')
            name = (item.get('name') or '').strip()
            if not name:
                continue
            out.append({
                'name': name,
                'dosage': (item.get('dosage') or '').strip(),
                'note': (item.get('note') or '').strip(),
            })
        return out


class HealthProfileSerializer(serializers.ModelSerializer):
    """详情序列化器：含血型 + 过敏/慢性病/用药明细。"""
    allergies = AllergyField(required=False)
    chronic_conditions = ChronicConditionField(required=False)
    medications = MedicationField(required=False)

    class Meta:
        model = HealthProfile
        fields = (
            'blood_type', 'allergies', 'chronic_conditions', 'medications',
            'updated_at',
        )
        read_only_fields = ('updated_at',)


class HealthProfileBriefSerializer(serializers.ModelSerializer):
    """列表用的轻量版（仅血型）。"""
    class Meta:
        model = HealthProfile
        fields = ('blood_type', 'updated_at')
        read_only_fields = ('updated_at',)


class MemberHealthProfileSerializer(serializers.ModelSerializer):
    """成员 + 健康档案，用于列表视图。"""
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    birthday = serializers.SerializerMethodField()
    health_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'display_name', 'avatar_url', 'birthday', 'health_profile')

    def get_birthday(self, obj):
        try:
            return obj.profile.birthday.isoformat() if obj.profile.birthday else None
        except Exception:
            return None

    def get_display_name(self, obj):
        try:
            return obj.profile.display_name
        except Exception:
            return obj.username

    def get_avatar_url(self, obj):
        try:
            if obj.profile.avatar:
                request = self.context.get('request')
                url = obj.profile.avatar.url
                return request.build_absolute_uri(url) if request else url
        except Exception:
            pass
        return None

    def get_health_profile(self, obj):
        try:
            hp = obj.health_profile
        except HealthProfile.DoesNotExist:
            hp = HealthProfile.objects.create(user=obj)
        return HealthProfileBriefSerializer(hp).data


class MetricField(serializers.JSONField):
    """校验健康指标为 [{name, value, unit, reference, abnormal}] 列表。"""
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if not isinstance(data, list):
            raise serializers.ValidationError('指标必须是列表')
        out = []
        for item in data:
            if not isinstance(item, dict):
                raise serializers.ValidationError('每个指标必须是对象')
            name = (item.get('name') or '').strip()
            if not name:
                continue
            value = item.get('value')
            if value not in (None, ''):
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    raise serializers.ValidationError(f'指标「{name}」数值必须为数字')
            else:
                value = None
            out.append({
                'name': name,
                'value': value,
                'unit': (item.get('unit') or '').strip(),
                'reference': (item.get('reference') or '').strip(),
                'abnormal': bool(item.get('abnormal')),
            })
        return out


class CheckupResultSerializer(serializers.ModelSerializer):
    metrics = MetricField(required=False)

    class Meta:
        model = CheckupResult
        fields = (
            'id', 'plan', 'visit_date', 'hospital', 'items',
            'conclusion', 'advice', 'metrics', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'plan', 'created_at', 'updated_at')


class CheckupPlanSerializer(serializers.ModelSerializer):
    result_summary = serializers.SerializerMethodField()

    class Meta:
        model = CheckupPlan
        fields = (
            'id', 'user', 'name', 'scheduled_date', 'frequency',
            'interval_months', 'status', 'result_summary', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_result_summary(self, obj):
        result = getattr(obj, 'result', None)
        if not result:
            return None
        return {
            'visit_date': result.visit_date.isoformat(),
            'hospital': result.hospital,
            'abnormal_count': result.abnormal_count(),
        }

    def validate(self, attrs):
        freq = attrs.get('frequency', getattr(self.instance, 'frequency', 'once'))
        interval = attrs.get('interval_months', getattr(self.instance, 'interval_months', None))
        if freq == 'every_n_months' and not interval:
            raise serializers.ValidationError('每N个月频次需填写间隔月数')
        return attrs


class HealthAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    is_image = serializers.BooleanField(read_only=True)

    class Meta:
        model = HealthAttachment
        fields = (
            'id', 'name', 'size_bytes', 'content_type', 'file_url',
            'is_image', 'uploaded_at', 'checkup_result', 'vaccination_record',
            'medical_visit',
        )
        read_only_fields = ('id', 'size_bytes', 'content_type', 'uploaded_at')

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class VaccinePlanSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = VaccinePlan
        fields = (
            'id', 'user', 'vaccine_name', 'dose_number', 'scheduled_date',
            'status', 'is_overdue', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class VaccinationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = VaccinationRecord
        fields = (
            'id', 'plan', 'administered_date', 'location',
            'brand_batch', 'note', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'plan', 'created_at', 'updated_at')


class HealthReminderSettingsSerializer(serializers.ModelSerializer):
    ALLOWED_LEAD = {0, 1, 3, 7, 14}

    class Meta:
        model = HealthReminderSettings
        fields = ('vaccine_lead_days', 'checkup_lead_days', 'followup_lead_days', 'updated_at')
        read_only_fields = ('updated_at',)

    def validate(self, attrs):
        for f in ('vaccine_lead_days', 'checkup_lead_days', 'followup_lead_days'):
            if f in attrs and attrs[f] not in self.ALLOWED_LEAD:
                raise serializers.ValidationError(f'{f} 只能是 0/1/3/7/14')
        return attrs


class MedicalVisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalVisit
        fields = (
            'id', 'user', 'visit_date', 'hospital', 'department',
            'visit_type', 'diagnosis', 'treatment', 'doctor',
            'followup_date', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
