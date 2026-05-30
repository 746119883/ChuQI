from rest_framework import serializers
from .models import TaskList, Task
from notes.serializers import UserSerializer


class TaskSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    completed_by = UserSerializer(read_only=True)

    class Meta:
        model = Task
        fields = (
            'id', 'list', 'title', 'completed',
            'completed_at', 'completed_by',
            'created_by', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'completed_at', 'completed_by',
            'created_by', 'created_at', 'updated_at',
        )

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class TaskListSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    total = serializers.SerializerMethodField()
    done = serializers.SerializerMethodField()

    class Meta:
        model = TaskList
        fields = (
            'id', 'name', 'description', 'is_shared',
            'owner',
            'total', 'done',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'owner',
            'total', 'done',
            'created_at', 'updated_at',
        )

    def get_total(self, obj):
        c = getattr(obj, '_total', None)
        return c if c is not None else obj.tasks.count()

    def get_done(self, obj):
        c = getattr(obj, '_done', None)
        return c if c is not None else obj.tasks.filter(completed=True).count()

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)
