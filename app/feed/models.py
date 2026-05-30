from django.db import models
from django.contrib.auth.models import User


VISIBILITY_CHOICES = [
    ('family', '家人可见'),
    ('private', '仅自己'),
]


class Moment(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='moments',
        verbose_name='作者',
    )
    content = models.TextField('内容', blank=True)
    visibility = models.CharField(
        '可见范围',
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='family',
    )
    created_at = models.DateTimeField('发布时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '动态'
        verbose_name_plural = '动态'
        ordering = ['-created_at']

    def __str__(self):
        preview = self.content[:30] or '(无文字)'
        return f'[{self.author.username}] {preview}'


class MomentImage(models.Model):
    """一条动态的图片。来源二选一：本地上传 (image) 或 引用 Immich (immich_asset_id)。"""
    moment = models.ForeignKey(
        Moment,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField(upload_to='moments/%Y/%m/', blank=True, null=True)
    immich_asset_id = models.CharField(
        'Immich asset id', max_length=64, blank=True, default='', db_index=True,
    )
    order = models.PositiveSmallIntegerField('顺序', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = '动态图片'
        verbose_name_plural = '动态图片'

    def __str__(self):
        src = 'immich' if self.immich_asset_id else 'local'
        return f'Image#{self.id} ({src}) for Moment#{self.moment_id}'

    @property
    def source(self) -> str:
        return 'immich' if self.immich_asset_id else 'local'


REACTION_EMOJIS = [
    ('like', '👍'),
    ('love', '❤️'),
    ('haha', '😂'),
    ('wow', '😮'),
    ('sad', '😢'),
    ('celebrate', '🎉'),
]
# key -> emoji 字符，序列化/通知里复用
EMOJI_CHAR = dict(REACTION_EMOJIS)


class Reaction(models.Model):
    """对动态的表情回应。每人每条动态只保留一个表情(可切换/取消)。"""
    moment = models.ForeignKey(
        Moment,
        on_delete=models.CASCADE,
        related_name='reactions',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reactions',
    )
    emoji = models.CharField(max_length=10, choices=REACTION_EMOJIS, default='like')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('moment', 'user')
        verbose_name = '表情回应'
        verbose_name_plural = '表情回应'

    def __str__(self):
        return f'{self.user.username} {self.emoji} -> Moment#{self.moment_id}'


class Comment(models.Model):
    moment = models.ForeignKey(
        Moment,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    content = models.TextField('内容')
    created_at = models.DateTimeField('发表时间', auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = '评论'
        verbose_name_plural = '评论'

    def __str__(self):
        return f'[{self.author.username}] {self.content[:30]}'
