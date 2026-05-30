from django.contrib.auth.models import User
from django.db import models


MEAL_TYPES = [
    ('breakfast', '早餐'),
    ('lunch', '午餐'),
    ('dinner', '晚餐'),
    ('snack', '加餐'),
]

# 就餐方式：在家做 / 点外卖 / 出去吃
OPTION_KINDS = [
    ('home', '在家做'),
    ('takeout', '外卖'),
    ('dineout', '出去吃'),
]


class DiningOption(models.Model):
    """自定义就餐快捷选项：够不上写成菜谱、但常吃的去处。

    例如「楼下沙县」「点麦当劳」「下馆子」。家庭共享，进摇号池。
    """
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dining_options',
        verbose_name='添加人',
    )
    name = models.CharField('名称', max_length=100)
    kind = models.CharField('方式', max_length=10, choices=OPTION_KINDS, default='dineout')
    note = models.CharField('备注', max_length=200, blank=True)
    # 摇号权重：爱吃的调高，1~10 之间。停用后不进池但保留历史。
    weight = models.PositiveSmallIntegerField('权重', default=1)
    is_active = models.BooleanField('启用', default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '就餐选项'
        verbose_name_plural = '就餐选项'
        ordering = ['-is_active', 'kind', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_kind_display()})'


class MealLog(models.Model):
    """一餐吃了什么的记录。三选一来源：菜谱 / 就餐选项 / 自由文本。

    既是家庭饮食回忆，也是「摇一摇」排除最近重样的依据。
    """
    recorder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='meal_logs',
        verbose_name='记录人',
    )
    date = models.DateField('日期')
    meal_type = models.CharField('餐次', max_length=10, choices=MEAL_TYPES, default='dinner')

    recipe = models.ForeignKey(
        'recipes.Recipe',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='meal_logs',
        verbose_name='菜谱',
    )
    option = models.ForeignKey(
        DiningOption,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='meal_logs',
        verbose_name='就餐选项',
    )
    custom_name = models.CharField('自定义', max_length=100, blank=True)
    note = models.CharField('备注', max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '用餐记录'
        verbose_name_plural = '用餐记录'
        ordering = ['-date', 'meal_type', '-id']
        indexes = [
            models.Index(fields=['-date']),
        ]

    def __str__(self):
        return f'{self.date} {self.get_meal_type_display()}: {self.display_name}'

    @property
    def display_name(self):
        if self.recipe_id and self.recipe:
            return self.recipe.title
        if self.option_id and self.option:
            return self.option.name
        return self.custom_name or '(未填)'
