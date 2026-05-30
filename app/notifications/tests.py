"""站内通知跨用户隔离测试:只能看/操作自己的通知。"""
from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import Notification


class NotificationIsolationTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')

    def _notif(self, recipient, actor, is_read=False):
        return Notification.objects.create(
            recipient=recipient, actor=actor, verb='comment',
            text='测试通知', is_read=is_read,
        )

    def _items(self, resp):
        d = resp.data
        return d['results'] if isinstance(d, dict) and 'results' in d else d

    def test_list_only_own_notifications(self):
        mine = self._notif(self.alice, self.bob)
        self._notif(self.bob, self.alice)  # 别人的,不应出现
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/notifications/')
        self.assertEqual(resp.status_code, 200)
        items = self._items(resp)
        self.assertEqual([i['id'] for i in items], [mine.id])

    def test_unread_count_only_own(self):
        self._notif(self.alice, self.bob, is_read=False)
        self._notif(self.alice, self.bob, is_read=True)
        self._notif(self.bob, self.alice, is_read=False)
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/notifications/unread-count/')
        self.assertEqual(resp.data['count'], 1)

    def test_cannot_mark_others_notification_read(self):
        """尝试已读他人通知:不应真正改动对方的数据。"""
        n = self._notif(self.bob, self.alice, is_read=False)
        self.client.force_authenticate(self.alice)
        resp = self.client.post(f'/api/notifications/{n.id}/read/')
        self.assertEqual(resp.status_code, 200)
        n.refresh_from_db()
        self.assertFalse(n.is_read)  # bob 的通知仍未读

    def test_mark_own_notification_read(self):
        n = self._notif(self.alice, self.bob, is_read=False)
        self.client.force_authenticate(self.alice)
        self.client.post(f'/api/notifications/{n.id}/read/')
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_mark_all_read_only_affects_own(self):
        self._notif(self.alice, self.bob, is_read=False)
        self._notif(self.alice, self.bob, is_read=False)
        bob_n = self._notif(self.bob, self.alice, is_read=False)
        self.client.force_authenticate(self.alice)
        resp = self.client.post('/api/notifications/mark-all-read/')
        self.assertEqual(resp.data['updated'], 2)
        bob_n.refresh_from_db()
        self.assertFalse(bob_n.is_read)  # bob 的不受影响

    def test_unauthenticated_blocked(self):
        self.assertEqual(self.client.get('/api/notifications/').status_code, 401)
