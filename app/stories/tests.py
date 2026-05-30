"""故事可见性 + 写保护边界测试。"""
from datetime import date

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import Story


class StoryVisibilityTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')

    def _titles(self, resp):
        data = resp.data['results'] if isinstance(resp.data, dict) and 'results' in resp.data else resp.data
        return {s['title'] for s in data}

    def _story(self, author, visibility, title):
        return Story.objects.create(
            author=author, title=title, date=date(2026, 1, 1), visibility=visibility,
        )

    def test_list_shows_family_and_own_private(self):
        self._story(self.alice, 'private', '我的私密故事')
        self._story(self.bob, 'family', '公开故事')
        self._story(self.bob, 'private', '别人私密故事')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/stories/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._titles(resp), {'我的私密故事', '公开故事'})

    def test_other_private_story_not_retrievable(self):
        s = self._story(self.bob, 'private', '别人私密')
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.get(f'/api/stories/{s.id}/').status_code, 404)

    def test_non_author_cannot_edit_family_story(self):
        s = self._story(self.bob, 'family', '公开故事')
        self.client.force_authenticate(self.alice)
        resp = self.client.patch(f'/api/stories/{s.id}/', {'title': '篡改'})
        self.assertIn(resp.status_code, (403, 404))
        s.refresh_from_db()
        self.assertEqual(s.title, '公开故事')

    def test_unauthenticated_blocked(self):
        self.assertEqual(self.client.get('/api/stories/').status_code, 401)
