from django.db import models
from django.contrib.auth.models import User


VISIBILITY = [
    ('family', '家人可见'),
    ('private', '仅自己'),
]


class Folder(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='folders',
        verbose_name='创建人',
    )
    name = models.CharField('文件夹名', max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级文件夹',
    )
    visibility = models.CharField('可见范围', max_length=20, choices=VISIBILITY, default='family')
    description = models.CharField('描述', max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '文件夹'
        verbose_name_plural = '文件夹'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_ancestors(self):
        """返回从根到自己的路径(含自己)。最多 20 层防环。"""
        nodes = [self]
        current = self.parent
        depth = 0
        while current and depth < 20:
            nodes.insert(0, current)
            current = current.parent
            depth += 1
        return nodes


class File(models.Model):
    uploader = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vault_files',
        verbose_name='上传者',
    )
    folder = models.ForeignKey(
        Folder,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='files',
        verbose_name='所在文件夹',
    )
    file = models.FileField('文件', upload_to='vault/%Y/%m/')
    name = models.CharField('显示名', max_length=300)
    size_bytes = models.PositiveBigIntegerField('大小', default=0)
    mime_type = models.CharField('MIME', max_length=100, blank=True)
    is_important = models.BooleanField('重要文件', default=False)
    visibility = models.CharField('可见范围', max_length=20, choices=VISIBILITY, default='family')
    description = models.CharField('备注', max_length=500, blank=True)
    expires_at = models.DateField('过期日期', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '文件'
        verbose_name_plural = '文件'
        ordering = ['-is_important', '-created_at']
        indexes = [
            models.Index(fields=['folder', '-is_important', '-created_at']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return self.name
