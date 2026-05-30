from rest_framework import serializers

from accounts.serializers import UserSerializer
from immich.client import asset_url

from .models import Trip, TripChecklistItem, TripItem


class TripChecklistItemSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = TripChecklistItem
        fields = (
            'id', 'trip', 'kind', 'kind_display', 'text',
            'checked', 'created_by', 'order', 'created_at',
        )
        read_only_fields = ('id', 'created_by', 'created_at')

    def validate_trip(self, trip):
        """家人可见的旅行，家人都能加清单；私密的只有 owner。"""
        request = self.context.get('request')
        if request and trip.visibility != 'family' and trip.owner != request.user:
            raise serializers.ValidationError('无权操作该旅行的清单')
        return trip


class TripItemSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_item_type_display', read_only=True)

    class Meta:
        model = TripItem
        fields = (
            'id', 'trip', 'date', 'time', 'item_type', 'type_display',
            'title', 'detail', 'location', 'order', 'created_at',
        )
        read_only_fields = ('id', 'created_at')

    def validate_trip(self, trip):
        request = self.context.get('request')
        if request and trip.owner != request.user:
            raise serializers.ValidationError('只能给自己的旅行加行程')
        return trip


class TripSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    item_count = serializers.SerializerMethodField()
    items = TripItemSerializer(many=True, read_only=True)
    checklist = TripChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Trip
        fields = (
            'id', 'owner', 'title', 'destination',
            'start_date', 'end_date', 'summary',
            'cover_url', 'cover_immich_asset_id', 'immich_album_id',
            'visibility', 'status', 'item_count', 'items', 'checklist',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'owner', 'cover_url', 'immich_album_id',
            'status', 'item_count', 'items', 'checklist', 'created_at', 'updated_at',
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

    def get_item_count(self, obj):
        # items 已 prefetch,用 len 复用缓存避免额外查询
        return len(obj.items.all())

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class TripListSerializer(TripSerializer):
    """列表用，去掉 items 详情。"""
    class Meta(TripSerializer.Meta):
        fields = (
            'id', 'owner', 'title', 'destination',
            'start_date', 'end_date',
            'cover_url', 'visibility', 'status', 'item_count',
            'created_at', 'updated_at',
        )
