from rest_framework import serializers

from accounts.serializers import UserSerializer

from .models import Note


# 兼容旧导入：其他 app 使用 `from notes.serializers import UserSerializer`
__all__ = ['UserSerializer', 'NoteSerializer']


class NoteSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    author_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Note
        fields = (
            'id', 'title', 'content',
            'author', 'author_id',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def create(self, validated_data):
        validated_data.pop('author_id', None)
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)
