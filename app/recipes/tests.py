"""菜谱可见性 + 写保护边界测试。"""
from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import Recipe


class RecipeVisibilityTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')

    def _names(self, resp):
        data = resp.data['results'] if isinstance(resp.data, dict) and 'results' in resp.data else resp.data
        return {r['title'] for r in data}

    def test_list_shows_family_and_own_private(self):
        Recipe.objects.create(author=self.alice, title='我的私房菜', visibility='private')
        Recipe.objects.create(author=self.bob, title='公开家常菜', visibility='family')
        Recipe.objects.create(author=self.bob, title='别人私房菜', visibility='private')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/recipes/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._names(resp), {'我的私房菜', '公开家常菜'})

    def test_other_private_recipe_not_retrievable(self):
        r = Recipe.objects.create(author=self.bob, title='别人私房菜', visibility='private')
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.get(f'/api/recipes/{r.id}/').status_code, 404)

    def test_non_author_cannot_edit_family_recipe(self):
        r = Recipe.objects.create(author=self.bob, title='公开菜', visibility='family')
        self.client.force_authenticate(self.alice)
        resp = self.client.patch(f'/api/recipes/{r.id}/', {'title': '篡改'})
        self.assertIn(resp.status_code, (403, 404))
        r.refresh_from_db()
        self.assertEqual(r.title, '公开菜')

    def test_author_can_edit_own(self):
        r = Recipe.objects.create(author=self.alice, title='原名', visibility='family')
        self.client.force_authenticate(self.alice)
        resp = self.client.patch(f'/api/recipes/{r.id}/', {'title': '新名'})
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.title, '新名')

    def test_unauthenticated_blocked(self):
        self.assertEqual(self.client.get('/api/recipes/').status_code, 401)
