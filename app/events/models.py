from django.db import models
from django.contrib.auth.models import User


EVENT_TYPES = [
    ('general', '一般事件'),
    ('birthday', '生日'),
    ('anniversary', '纪念日'),
    ('memorial', '忌日'),
    ('holiday', '节日'),
]

VISIBILITY = [
    ('family', '家人可见'),
    ('private', '仅自己'),
]


class Event(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name='创建人',
    )
    title = models.CharField('标题', max_length=100)
    description = models.TextField('描述', blank=True)
    event_type = models.CharField('类型', max_length=20, choices=EVENT_TYPES, default='general')
    color = models.CharField('颜色', max_length=7, default='#3b82f6')
    visibility = models.CharField('可见范围', max_length=20, choices=VISIBILITY, default='family')

    # 日期 (存月日,可选年份)
    is_lunar = models.BooleanField('农历', default=False)
    date_year = models.IntegerField('原始年份(可选)', null=True, blank=True)
    date_month = models.IntegerField('月')
    date_day = models.IntegerField('日')

    # 时间
    all_day = models.BooleanField('全天', default=True)
    start_time = models.TimeField('开始时间', null=True, blank=True)
    end_time = models.TimeField('结束时间', null=True, blank=True)

    # 重复 (MVP 仅支持每年同月同日)
    yearly_recurring = models.BooleanField('每年重复', default=False)

    # 提醒 (仅存储,远期接邮件/推送)
    remind_days_before = models.IntegerField('提前提醒天数', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '日历事件'
        verbose_name_plural = '日历事件'

    def __str__(self):
        cal = '农历' if self.is_lunar else '公历'
        return f'{self.title} ({cal} {self.date_month}/{self.date_day})'
