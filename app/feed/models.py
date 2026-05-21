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
    moment = models.ForeignKey(
        Moment,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField(upload_to='moments/%Y/%m/')
    order = models.PositiveSmallIntegerField('顺序', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = '动态图片'
        verbose_name_plural = '动态图片'

    def __str__(self):
        return f'Image#{self.id} for Moment#{self.moment_id}'


class Reaction(models.Model):
    """点赞(后续可扩展心情类型)"""
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('moment', 'user')
        verbose_name = '点赞'
        verbose_name_plural = '点赞'

    def __str__(self):
        return f'{self.user.username} -> Moment#{self.moment_id}'


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
