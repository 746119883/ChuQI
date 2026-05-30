from rest_framework import serializers

from accounts.serializers import UserSerializer
from immich.client import asset_url

from .models import Story, StoryBlock


class StoryBlockSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    immich_thumbnail_url = serializers.SerializerMethodField()
    immich_preview_url = serializers.SerializerMethodField()

    class Meta:
        model = StoryBlock
        fields = (
            'id', 'kind', 'order',
            'text',
            'image_url',
            'immich_asset_id', 'immich_filename', 'immich_thumbnail_url', 'immich_preview_url',
            'caption',
        )
        read_only_fields = ('id', 'image_url', 'immich_thumbnail_url', 'immich_preview_url')

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url

    def get_immich_thumbnail_url(self, obj):
        if obj.immich_asset_id:
            url = asset_url(obj.immich_asset_id, 'thumbnail')
            request = self.context.get('request')
            return request.build_absolute_uri(url) if request else url
        return None

    def get_immich_preview_url(self, obj):
        if obj.immich_asset_id:
            url = asset_url(obj.immich_asset_id, 'preview')
            request = self.context.get('request')
            return request.build_absolute_uri(url) if request else url
        return None


class StorySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    blocks = StoryBlockSerializer(many=True, read_only=True)

    class Meta:
        model = Story
        fields = (
            'id', 'author',
            'title', 'date', 'summary',
            'cover_url', 'cover_immich_asset_id',
            'visibility',
            'blocks',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'author', 'cover_url', 'created_at', 'updated_at')

    def get_cover_url(self, obj):
        request = self.context.get('request')

        def absolute(url):
            return request.build_absolute_uri(url) if request else url

        if obj.cover_immich_asset_id:
            return absolute(asset_url(obj.cover_immich_asset_id, 'preview'))
        if obj.cover:
            return absolute(obj.cover.url)
        return None

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class StoryListSerializer(serializers.ModelSerializer):
    """列表用精简版（不含 blocks 详情）。"""
    author = UserSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    block_count = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = (
            'id', 'author',
            'title', 'date', 'summary',
            'cover_url', 'block_count',
            'visibility',
            'created_at', 'updated_at',
        )

    def get_cover_url(self, obj):
        request = self.context.get('request')

        def absolute(url):
            return request.build_absolute_uri(url) if request else url

        if obj.cover_immich_asset_id:
            return absolute(asset_url(obj.cover_immich_asset_id, 'thumbnail'))
        if obj.cover:
            return absolute(obj.cover.url)
        return None

    def get_block_count(self, obj):
        c = getattr(obj, '_block_count', None)
        return c if c is not None else obj.blocks.count()
