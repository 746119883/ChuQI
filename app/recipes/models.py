from django.contrib.auth.models import User
from django.db import models


CATEGORY_CHOICES = [
    ('meat', '荤菜'),
    ('veg', '素菜'),
    ('soup', '汤羹'),
    ('staple', '主食'),
    ('breakfast', '早餐'),
    ('dessert', '甜点'),
    ('drink', '饮品'),
    ('other', '其他'),
]

DIFFICULTY_CHOICES = [
    ('easy', '简单'),
    ('medium', '中等'),
    ('hard', '有点难'),
]

VISIBILITY_CHOICES = [
    ('family', '家人可见'),
    ('private', '仅自己'),
]


class Recipe(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recipes',
        verbose_name='作者',
    )
    title = models.CharField('菜名', max_length=100)
    description = models.TextField('简介', blank=True)
    category = models.CharField('分类', max_length=20, choices=CATEGORY_CHOICES, default='other')
    tags = models.JSONField('标签', default=list, blank=True)          # ["快手","下饭"]
    servings = models.CharField('份量', max_length=30, blank=True)      # "2-3 人"
    total_time_min = models.PositiveIntegerField('耗时(分钟)', null=True, blank=True)
    difficulty = models.CharField('难度', max_length=10, choices=DIFFICULTY_CHOICES, default='easy')

    # [{"name":"鸡蛋","amount":"2 个"}, ...]
    ingredients = models.JSONField('食材', default=list, blank=True)
    # [{"text":"打蛋液加盐"}, ...]
    steps = models.JSONField('步骤', default=list, blank=True)

    # 封面：本地上传 或 引用 Immich，二选一
    cover = models.ImageField('封面', upload_to='recipes/%Y/%m/', blank=True, null=True)
    cover_immich_asset_id = models.CharField(max_length=64, blank=True, default='')

    visibility = models.CharField('可见范围', max_length=20, choices=VISIBILITY_CHOICES, default='family')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '菜谱'
        verbose_name_plural = '菜谱'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title
