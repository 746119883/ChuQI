from datetime import date, timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from recipes.models import Recipe

from .models import DiningOption, MealLog


class MealsTestBase(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')


class RollTests(MealsTestBase):
    def _roll(self, **params):
        self.client.force_authenticate(self.alice)
        return self.client.get('/api/meal-logs/roll/', params)

    def test_empty_pool_returns_null_main(self):
        resp = self._roll(exclude_days=0)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['main'])
        self.assertEqual(resp.data['pool_size'], 0)

    def test_pool_merges_recipes_and_options(self):
        Recipe.objects.create(author=self.alice, title='番茄炒蛋', visibility='family')
        DiningOption.objects.create(created_by=self.alice, name='楼下沙县')
        resp = self._roll(exclude_days=0, count=10)
        self.assertEqual(resp.data['pool_size'], 2)

    def test_excludes_recent_meals(self):
        r = Recipe.objects.create(author=self.alice, title='红烧肉', visibility='family')
        MealLog.objects.create(
            recorder=self.alice, date=timezone.localdate(),
            meal_type='dinner', recipe=r,
        )
        # 默认排除最近 3 天 -> 池里不应有红烧肉
        resp = self._roll(source='recipe', exclude_days=3)
        self.assertEqual(resp.data['pool_size'], 0)
        # exclude_days=0 -> 不排除
        resp = self._roll(source='recipe', exclude_days=0)
        self.assertEqual(resp.data['pool_size'], 1)

    def test_old_meals_not_excluded(self):
        r = Recipe.objects.create(author=self.alice, title='糖醋排骨', visibility='family')
        MealLog.objects.create(
            recorder=self.alice, date=timezone.localdate() - timedelta(days=10),
            meal_type='dinner', recipe=r,
        )
        resp = self._roll(source='recipe', exclude_days=3)
        self.assertEqual(resp.data['pool_size'], 1)

    def test_source_option_only(self):
        Recipe.objects.create(author=self.alice, title='清蒸鱼', visibility='family')
        DiningOption.objects.create(created_by=self.alice, name='点麦当劳', kind='takeout')
        resp = self._roll(source='option', exclude_days=0)
        self.assertEqual(resp.data['pool_size'], 1)
        self.assertEqual(resp.data['main']['type'], 'option')

    def test_kind_filter(self):
        DiningOption.objects.create(created_by=self.alice, name='楼下沙县', kind='dineout')
        DiningOption.objects.create(created_by=self.alice, name='点麦当劳', kind='takeout')
        resp = self._roll(kind='takeout', exclude_days=0)
        self.assertEqual(resp.data['pool_size'], 1)
        self.assertEqual(resp.data['main']['name'], '点麦当劳')

    def test_inactive_option_excluded(self):
        DiningOption.objects.create(
            created_by=self.alice, name='已停用', is_active=False,
        )
        resp = self._roll(source='option', exclude_days=0)
        self.assertEqual(resp.data['pool_size'], 0)

    def test_private_recipe_of_others_excluded(self):
        Recipe.objects.create(author=self.bob, title='私房菜', visibility='private')
        Recipe.objects.create(author=self.bob, title='公开菜', visibility='family')
        resp = self._roll(source='recipe', exclude_days=0)
        self.assertEqual(resp.data['pool_size'], 1)
        self.assertEqual(resp.data['main']['name'], '公开菜')

    def test_home_option_included_in_recipe_scope(self):
        """在家做(source=recipe)应包含 kind=home 的就餐选项,而非只有菜谱。"""
        Recipe.objects.create(author=self.alice, title='番茄炒蛋', visibility='family')
        DiningOption.objects.create(created_by=self.alice, name='妈妈的红烧肉', kind='home')
        resp = self._roll(source='recipe', exclude_days=0, count=10)
        names = {c['name'] for c in [resp.data['main']] + resp.data['alternatives']}
        self.assertEqual(resp.data['pool_size'], 2)
        self.assertEqual(names, {'番茄炒蛋', '妈妈的红烧肉'})

    def test_home_option_not_in_takeout_scope(self):
        """在家做的选项不应出现在外卖摇号里。"""
        DiningOption.objects.create(created_by=self.alice, name='妈妈的红烧肉', kind='home')
        DiningOption.objects.create(created_by=self.alice, name='麦当劳', kind='takeout')
        resp = self._roll(source='option', kind='takeout', exclude_days=0)
        self.assertEqual(resp.data['pool_size'], 1)
        self.assertEqual(resp.data['main']['name'], '麦当劳')


class MealLogTests(MealsTestBase):
    def test_requires_a_source(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.post('/api/meal-logs/', {
            'date': '2026-05-29', 'meal_type': 'dinner',
        })
        self.assertEqual(resp.status_code, 400)

    def test_custom_name_is_accepted(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.post('/api/meal-logs/', {
            'date': '2026-05-29', 'meal_type': 'dinner', 'custom_name': '剩菜',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['recorder']['username'], 'alice')

    def test_cannot_edit_others_log(self):
        log = MealLog.objects.create(
            recorder=self.alice, date=date(2026, 5, 29),
            meal_type='dinner', custom_name='火锅',
        )
        self.client.force_authenticate(self.bob)
        resp = self.client.patch(f'/api/meal-logs/{log.id}/', {'note': 'hi'})
        self.assertEqual(resp.status_code, 403)

    def test_can_read_others_log(self):
        MealLog.objects.create(
            recorder=self.alice, date=date(2026, 5, 29),
            meal_type='dinner', custom_name='火锅',
        )
        self.client.force_authenticate(self.bob)
        resp = self.client.get('/api/meal-logs/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)


class DiningOptionTests(MealsTestBase):
    def test_weight_clamped_to_range(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.post('/api/dining-options/', {
            'name': '超爱吃', 'kind': 'dineout', 'weight': 999,
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['weight'], 10)

    def test_cannot_delete_others_option(self):
        opt = DiningOption.objects.create(created_by=self.alice, name='楼下沙县')
        self.client.force_authenticate(self.bob)
        resp = self.client.delete(f'/api/dining-options/{opt.id}/')
        self.assertEqual(resp.status_code, 403)
