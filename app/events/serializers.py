from rest_framework import serializers
from .models import Event
from notes.serializers import UserSerializer


class EventSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)

    class Meta:
        model = Event
        fields = (
            'id', 'owner',
            'title', 'description',
            'event_type', 'color', 'visibility',
            'is_lunar', 'date_year', 'date_month', 'date_day',
            'all_day', 'start_time', 'end_time',
            'yearly_recurring',
            'remind_days_before',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'owner', 'created_at', 'updated_at')

    def validate(self, data):
        is_lunar = data.get('is_lunar', getattr(self.instance, 'is_lunar', False))
        m = data.get('date_month', getattr(self.instance, 'date_month', None))
        d = data.get('date_day', getattr(self.instance, 'date_day', None))
        if m is not None and (m < 1 or m > 12):
            raise serializers.ValidationError({'date_month': '月份必须在 1-12'})
        if d is not None:
            max_d = 30 if is_lunar else 31
            if d < 1 or d > max_d:
                raise serializers.ValidationError({'date_day': f'日必须在 1-{max_d}'})
        return data

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class OccurrenceSerializer(serializers.Serializer):
    """展开后的单个发生:公历日期 + 事件 + 农历注释"""
    date = serializers.DateField()
    lunar_label = serializers.CharField(allow_blank=True)
    event = EventSerializer()
