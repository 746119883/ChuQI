from datetime import date as date_cls

from django.contrib.auth.models import User
from django.db import models


VISIBILITY_CHOICES = [
    ('family', '家人可见'),
    ('private', '仅自己'),
]

ITEM_TYPES = [
    ('transport', '交通'),
    ('hotel', '住宿'),
    ('activity', '景点活动'),
    ('food', '餐饮'),
    ('ticket', '门票预订'),
    ('info', '实用信息'),
    ('other', '其他'),
]

CHECKLIST_KINDS = [
    ('bring', '要带'),
    ('buy', '要买'),
]


class Trip(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='trips',
        verbose_name='创建人',
    )
    title = models.CharField('标题', max_length=100)            # "2026 春节·三亚"
    destination = models.CharField('目的地', max_length=100, blank=True)
    start_date = models.DateField('出发日期')
    end_date = models.DateField('返回日期', null=True, blank=True)
    summary = models.TextField('备注/实用信息', blank=True)

    cover = models.ImageField('封面', upload_to='trips/%Y/%m/', blank=True, null=True)
    cover_immich_asset_id = models.CharField(max_length=64, blank=True, default='')

    # 一键归集生成的 Immich 相册 id（生成后记录，避免重复建）
    immich_album_id = models.CharField(max_length=64, blank=True, default='')

    visibility = models.CharField('可见范围', max_length=20, choices=VISIBILITY_CHOICES, default='family')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '旅行'
        verbose_name_plural = '旅行'
        ordering = ['-start_date', '-id']

    def __str__(self):
        return self.title

    @property
    def status(self):
        today = date_cls.today()
        if self.start_date > today:
            return 'planning'
        end = self.end_date or self.start_date
        if end < today:
            return 'done'
        return 'ongoing'


class TripItem(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='items',
    )
    date = models.DateField('日期')
    time = models.TimeField('时间', null=True, blank=True)
    item_type = models.CharField('类型', max_length=20, choices=ITEM_TYPES, default='activity')
    title = models.CharField('标题', max_length=200)            # "MU5137 浦东→三亚"
    detail = models.TextField('详情', blank=True)               # 航班号/确认号/地址
    location = models.CharField('地点', max_length=200, blank=True)
    order = models.PositiveSmallIntegerField('排序', default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '行程项'
        verbose_name_plural = '行程项'
        ordering = ['date', 'time', 'order', 'id']

    def __str__(self):
        return f'{self.date} {self.title}'


class TripChecklistItem(models.Model):
    """旅行清单：去之前要带的 / 回来要买的。家人可共同维护。"""
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='checklist',
    )
    kind = models.CharField('类型', max_length=10, choices=CHECKLIST_KINDS, default='bring')
    text = models.CharField('内容', max_length=200)
    checked = models.BooleanField('已完成', default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='trip_checklist_items',
    )
    order = models.PositiveSmallIntegerField('排序', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '旅行清单项'
        verbose_name_plural = '旅行清单项'
        ordering = ['kind', 'checked', 'order', 'id']

    def __str__(self):
        return f'[{"x" if self.checked else " "}] {self.text}'
