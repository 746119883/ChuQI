from django.contrib.auth.models import User
from django.db import models


VISIBILITY_CHOICES = [
    ('family', '家人可见'),
    ('private', '仅自己'),
]

BLOCK_KINDS = [
    ('text', '文字'),
    ('photo', '本地图片'),
    ('immich', 'Immich 图片'),
]


class Story(models.Model):
    """家庭相册故事：图文混排的「那年那月」记录。"""
    author = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='stories', verbose_name='作者',
    )
    title = models.CharField('标题', max_length=100)
    date = models.DateField('故事日期')
    summary = models.CharField('简介', max_length=300, blank=True)

    # 封面：本地上传 或 Immich，二选一
    cover = models.ImageField('封面', upload_to='stories/covers/%Y/%m/', blank=True, null=True)
    cover_immich_asset_id = models.CharField(max_length=64, blank=True, default='')

    visibility = models.CharField(
        '可见范围', max_length=20, choices=VISIBILITY_CHOICES, default='family',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '家庭故事'
        verbose_name_plural = '家庭故事'
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.date} {self.title}'


class StoryBlock(models.Model):
    """故事里的一个内容块（文字 / 本地图 / Immich 图），按 order 排列。"""
    story = models.ForeignKey(
        Story, on_delete=models.CASCADE,
        related_name='blocks', verbose_name='故事',
    )
    kind = models.CharField('类型', max_length=10, choices=BLOCK_KINDS, default='text')
    order = models.PositiveSmallIntegerField('排序', default=0)

    # kind=text
    text = models.TextField('文字内容', blank=True)

    # kind=photo
    image = models.ImageField('图片', upload_to='stories/blocks/%Y/%m/', blank=True, null=True)

    # kind=immich
    immich_asset_id = models.CharField('Immich asset id', max_length=64, blank=True, default='')
    # 存一份 Immich 图片的原始文件名，方便展示
    immich_filename = models.CharField(max_length=200, blank=True, default='')

    # 图片块可附带说明（photo/immich 都用）
    caption = models.CharField('图片说明', max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '故事内容块'
        verbose_name_plural = '故事内容块'
        ordering = ['order', 'id']

    def __str__(self):
        return f'Story#{self.story_id} block#{self.id} ({self.kind})'
