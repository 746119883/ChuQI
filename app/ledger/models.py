from django.contrib.auth.models import User
from django.db import models


ENTRY_TYPES = [
    ('expense', '支出'),
    ('income', '收入'),
]

# 面向"家庭大额"的分类，不追求记账软件的细致
CATEGORY_CHOICES = [
    ('food', '餐饮'),
    ('shopping', '购物'),
    ('appliance', '家电'),
    ('travel', '旅行'),
    ('medical', '医疗'),
    ('education', '教育'),
    ('social', '人情红包'),
    ('housing', '住房物业'),
    ('transport', '交通'),
    ('salary', '工资'),
    ('bonus', '奖金'),
    ('other', '其他'),
]

VISIBILITY_CHOICES = [
    ('family', '家人可见'),
    ('private', '仅自己'),
]


class LedgerEntry(models.Model):
    recorder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ledger_entries',
        verbose_name='记录人',
    )
    entry_type = models.CharField('类型', max_length=10, choices=ENTRY_TYPES, default='expense')
    amount = models.DecimalField('金额', max_digits=12, decimal_places=2)
    category = models.CharField('分类', max_length=20, choices=CATEGORY_CHOICES, default='other')
    title = models.CharField('说明', max_length=100)
    note = models.TextField('备注', blank=True)
    date = models.DateField('日期')
    visibility = models.CharField('可见范围', max_length=20, choices=VISIBILITY_CHOICES, default='family')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '账目'
        verbose_name_plural = '账目'
        ordering = ['-date', '-id']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['entry_type']),
        ]

    def __str__(self):
        sign = '-' if self.entry_type == 'expense' else '+'
        return f'{sign}{self.amount} {self.title}'
