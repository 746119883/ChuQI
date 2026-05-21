from django.db import models
from django.contrib.auth.models import User


class TaskList(models.Model):
    """清单(购物/待办/出行打包...)"""
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='task_lists',
        verbose_name='创建人',
    )
    name = models.CharField('名称', max_length=100)
    description = models.CharField('描述', max_length=300, blank=True)
    is_shared = models.BooleanField('家人共享', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '清单'
        verbose_name_plural = '清单'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class Task(models.Model):
    list = models.ForeignKey(
        TaskList,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='所属清单',
    )
    title = models.CharField('内容', max_length=300)
    completed = models.BooleanField('已完成', default=False)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_tasks',
        verbose_name='完成人',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks',
        verbose_name='创建人',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '任务'
        verbose_name_plural = '任务'
        # 未完成在前(按创建时间),已完成在后(按完成时间)
        ordering = ['completed', 'created_at']

    def __str__(self):
        return f'[{"x" if self.completed else " "}] {self.title}'
