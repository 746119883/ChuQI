from django.contrib.auth.models import User
from django.db import models


VISIBILITY_CHOICES = [
    ('family', '家人可见'),
    ('private', '仅自己'),
]

MILESTONE_TYPES = [
    ('birth', '新生'),
    ('marriage', '婚姻'),
    ('home', '安家'),
    ('graduation', '毕业'),
    ('career', '事业'),
    ('travel', '旅行'),
    ('pet', '宠物'),
    ('honor', '喜事'),
    ('other', '其他'),
]

# 每种类型的默认 emoji（前端也有同名映射，这里给后端/通知兜底）
TYPE_ICONS = {
    'birth': '👶',
    'marriage': '💍',
    'home': '🏠',
    'graduation': '🎓',
    'career': '💼',
    'travel': '✈️',
    'pet': '🐾',
    'honor': '🎉',
    'other': '⭐',
}


class Milestone(models.Model):
    """家庭大事记：值得记住的大日子（宝宝出生、买房、结婚纪念……）。"""
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='milestones', verbose_name='记录人',
    )
    title = models.CharField('标题', max_length=120)
    date = models.DateField('日期')
    milestone_type = models.CharField('类型', max_length=20, choices=MILESTONE_TYPES, default='other')
    description = models.TextField('详情', blank=True)

    cover = models.ImageField('封面', upload_to='milestones/%Y/%m/', blank=True, null=True)
    cover_immich_asset_id = models.CharField(max_length=64, blank=True, default='')

    visibility = models.CharField('可见范围', max_length=20, choices=VISIBILITY_CHOICES, default='family')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '大事记'
        verbose_name_plural = '大事记'
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.date} {self.title}'

    @property
    def icon(self):
        return TYPE_ICONS.get(self.milestone_type, '⭐')
