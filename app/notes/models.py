from django.db import models
from django.contrib.auth.models import User


class Note(models.Model):
    title = models.CharField('标题', max_length=200)
    content = models.TextField('内容', blank=True)
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name='作者',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '笔记'
        verbose_name_plural = '笔记'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
