from django.utils import timezone
from rest_framework import serializers
from .models import Folder, File
from notes.serializers import UserSerializer


class FolderBriefSerializer(serializers.ModelSerializer):
    """用于面包屑(只要 id 和 name)"""
    class Meta:
        model = Folder
        fields = ('id', 'name')


class FolderSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    item_count = serializers.SerializerMethodField()
    ancestors = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = (
            'id', 'name', 'parent', 'visibility', 'description',
            'owner', 'item_count', 'ancestors',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'owner', 'item_count', 'ancestors',
            'created_at', 'updated_at',
        )

    def get_item_count(self, obj):
        # annotate 已在 get_queryset 里注入 file_count / child_count，直接取
        return getattr(obj, 'file_count', 0) + getattr(obj, 'child_count', 0)

    def get_ancestors(self, obj):
        # 不含自己，只到 parent；parent 已通过 select_related 预加载
        path = []
        node = obj.parent
        depth = 0
        while node and depth < 20:
            path.insert(0, {'id': node.id, 'name': node.name})
            node = node.parent
            depth += 1
        return path

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class FileSerializer(serializers.ModelSerializer):
    uploader = UserSerializer(read_only=True)
    file = serializers.FileField(use_url=True, read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = (
            'id', 'uploader', 'folder',
            'file', 'name', 'size_bytes', 'mime_type',
            'is_important', 'visibility',
            'description', 'expires_at', 'is_expired',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'uploader', 'file', 'size_bytes', 'mime_type',
            'is_expired', 'created_at', 'updated_at',
        )

    def get_is_expired(self, obj):
        if obj.expires_at is None:
            return False
        return obj.expires_at < timezone.now().date()
