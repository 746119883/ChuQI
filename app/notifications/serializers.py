from rest_framework import serializers

from accounts.serializers import UserSerializer

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True, allow_null=True)
    verb_display = serializers.CharField(source='get_verb_display', read_only=True)
    moment_preview = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            'id', 'actor', 'verb', 'verb_display',
            'moment', 'comment', 'emoji', 'text',
            'moment_preview', 'is_read', 'created_at',
        )
        read_only_fields = fields

    def get_moment_preview(self, obj):
        if obj.moment_id and obj.moment:
            content = (obj.moment.content or '').strip()
            return content[:40] or '(图片动态)'
        return ''
