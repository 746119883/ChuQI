from rest_framework import serializers

from accounts.serializers import UserSerializer
from immich.client import asset_url

from .models import Milestone


class MilestoneSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    type_display = serializers.CharField(source='get_milestone_type_display', read_only=True)
    icon = serializers.CharField(read_only=True)
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = Milestone
        fields = (
            'id', 'created_by', 'title', 'date',
            'milestone_type', 'type_display', 'icon',
            'description', 'cover_url', 'cover_immich_asset_id',
            'visibility', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'created_by', 'type_display', 'icon', 'cover_url',
            'created_at', 'updated_at',
        )

    def _abs(self, url):
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def get_cover_url(self, obj):
        if obj.cover_immich_asset_id:
            return self._abs(asset_url(obj.cover_immich_asset_id, 'preview'))
        if obj.cover:
            return self._abs(obj.cover.url)
        return None
