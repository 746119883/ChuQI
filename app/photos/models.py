from django.db import models
from django.contrib.auth.models import User


class Album(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='albums',
        verbose_name='所有者',
    )
    name = models.CharField('相册名', max_length=100)
    description = models.TextField('描述', blank=True)
    cover_photo = models.ForeignKey(
        'Photo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='封面',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '相册'
        verbose_name_plural = '相册'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class Photo(models.Model):
    uploader = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name='上传者',
    )
    album = models.ForeignKey(
        Album,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='photos',
        verbose_name='相册',
    )
    image = models.ImageField('原图', upload_to='photos/original/%Y/%m/')
    thumbnail = models.ImageField(
        '缩略图',
        upload_to='photos/thumb/%Y/%m/',
        blank=True,
    )
    width = models.PositiveIntegerField('宽', default=0)
    height = models.PositiveIntegerField('高', default=0)
    size_bytes = models.PositiveBigIntegerField('文件大小', default=0)
    taken_at = models.DateTimeField('拍摄时间', null=True, blank=True)
    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)
    caption = models.CharField('说明', max_length=300, blank=True)

    class Meta:
        verbose_name = '照片'
        verbose_name_plural = '照片'
        ordering = ['-taken_at', '-uploaded_at']
        indexes = [
            models.Index(fields=['-taken_at']),
            models.Index(fields=['album', '-taken_at']),
        ]

    def __str__(self):
        return f'Photo#{self.id} by {self.uploader.username}'

    @property
    def display_date(self):
        return self.taken_at or self.uploaded_at


class Video(models.Model):
    uploader = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='videos',
        verbose_name='上传者',
    )
    album = models.ForeignKey(
        Album,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='videos',
        verbose_name='相册',
    )
    file = models.FileField('视频文件', upload_to='videos/original/%Y/%m/')
    poster = models.ImageField(
        '封面截图',
        upload_to='videos/poster/%Y/%m/',
        blank=True,
    )
    width = models.PositiveIntegerField('宽', default=0)
    height = models.PositiveIntegerField('高', default=0)
    duration = models.FloatField('时长(秒)', default=0)
    size_bytes = models.PositiveBigIntegerField('文件大小', default=0)
    taken_at = models.DateTimeField('拍摄时间', null=True, blank=True)
    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)
    caption = models.CharField('说明', max_length=300, blank=True)

    class Meta:
        verbose_name = '视频'
        verbose_name_plural = '视频'
        ordering = ['-taken_at', '-uploaded_at']
        indexes = [
            models.Index(fields=['-taken_at']),
            models.Index(fields=['album', '-taken_at']),
        ]

    def __str__(self):
        return f'Video#{self.id} by {self.uploader.username}'

    @property
    def display_date(self):
        return self.taken_at or self.uploaded_at
