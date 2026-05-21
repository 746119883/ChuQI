from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.response import Response

from .models import TaskList, Task
from .serializers import TaskListSerializer, TaskSerializer


class TaskListPermission(permissions.BasePermission):
    """清单本身:只有 owner 能改/删。共享列表家人都能看。"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.is_shared or obj.owner == request.user
        return obj.owner == request.user


class TaskListViewSet(viewsets.ModelViewSet):
    serializer_class = TaskListSerializer
    permission_classes = [permissions.IsAuthenticated, TaskListPermission]

    def get_queryset(self):
        user = self.request.user
        return (
            TaskList.objects
            .select_related('owner')
            .filter(Q(is_shared=True) | Q(owner=user))
        )


class TaskPermission(permissions.BasePermission):
    """任务:共享列表里的任何家人都能改;私密列表只有 list owner 能改。"""
    def has_object_permission(self, request, view, obj):
        tl = obj.list
        if tl.is_shared:
            return True
        return tl.owner == request.user


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, TaskPermission]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Task.objects
            .select_related('list', 'created_by', 'completed_by')
            .filter(Q(list__is_shared=True) | Q(list__owner=user))
        )
        list_id = self.request.query_params.get('list')
        if list_id:
            qs = qs.filter(list_id=list_id)
        return qs

    def perform_update(self, serializer):
        # 切换 completed 时,自动记录完成时间和完成人
        instance = serializer.instance
        was_completed = instance.completed
        new_completed = serializer.validated_data.get('completed', was_completed)

        if new_completed and not was_completed:
            serializer.save(
                completed_at=timezone.now(),
                completed_by=self.request.user,
            )
        elif not new_completed and was_completed:
            serializer.save(completed_at=None, completed_by=None)
        else:
            serializer.save()
