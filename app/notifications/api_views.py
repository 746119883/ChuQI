from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .reminders import run_reminders_for_user
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return (
            Notification.objects
            .filter(recipient=self.request.user)
            .select_related('actor', 'actor__profile', 'moment')[:50]
        )

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count()
        return Response({'count': count})

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        Notification.objects.filter(
            pk=pk, recipient=request.user,
        ).update(is_read=True)
        return Response({'ok': True})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).update(is_read=True)
        return Response({'updated': updated})

    @action(detail=False, methods=['post'], url_path='check-reminders')
    def check_reminders(self, request):
        """登录/刷新/每 10 分钟调一次。扫生日/事件/文件到期，生成站内提醒。
        幂等：同一条提醒同一天只生成一次（dedup_key）。
        """
        result = run_reminders_for_user(request.user)
        return Response(result)
