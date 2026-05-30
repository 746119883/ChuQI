from rest_framework import serializers

from accounts.serializers import UserSerializer

from .models import LedgerEntry


class LedgerEntrySerializer(serializers.ModelSerializer):
    recorder = UserSerializer(read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    type_display = serializers.CharField(source='get_entry_type_display', read_only=True)

    class Meta:
        model = LedgerEntry
        fields = (
            'id', 'recorder',
            'entry_type', 'type_display',
            'amount', 'category', 'category_display',
            'title', 'note', 'date', 'visibility',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'recorder', 'created_at', 'updated_at')

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('金额必须大于 0')
        return value

    def create(self, validated_data):
        validated_data['recorder'] = self.context['request'].user
        return super().create(validated_data)
