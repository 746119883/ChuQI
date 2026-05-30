"""行程可见性 + 写保护边界测试。"""
from datetime import date

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import Trip


class TripVisibilityTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')

    def _titles(self, resp):
        data = resp.data['results'] if isinstance(resp.data, dict) and 'results' in resp.data else resp.data
        return {t['title'] for t in data}

    def _trip(self, owner, visibility, title):
        return Trip.objects.create(
            owner=owner, title=title, start_date=date(2026, 2, 1), visibility=visibility,
        )

    def test_list_shows_family_and_own_private(self):
        self._trip(self.alice, 'private', '我的私密行程')
        self._trip(self.bob, 'family', '全家出游')
        self._trip(self.bob, 'private', '别人私密行程')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/trips/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._titles(resp), {'我的私密行程', '全家出游'})

    def test_other_private_trip_not_retrievable(self):
        t = self._trip(self.bob, 'private', '别人私密')
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.get(f'/api/trips/{t.id}/').status_code, 404)

    def test_non_owner_cannot_edit_family_trip(self):
        t = self._trip(self.bob, 'family', '全家出游')
        self.client.force_authenticate(self.alice)
        resp = self.client.patch(f'/api/trips/{t.id}/', {'title': '篡改'})
        self.assertIn(resp.status_code, (403, 404))
        t.refresh_from_db()
        self.assertEqual(t.title, '全家出游')

    def test_unauthenticated_blocked(self):
        self.assertEqual(self.client.get('/api/trips/').status_code, 401)
