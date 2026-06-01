from django.contrib.auth.models import User
from django.db import models


VERB_CHOICES = [
    ('comment', '评论了你的动态'),
    ('mention', '在评论里提到了你'),
    ('reaction', '回应了你的动态'),
    # 系统提醒类
    ('birthday', '生日提醒'),
    ('event', '日历提醒'),
    ('expiry', '文件到期提醒'),
    # 健康提醒类
    ('health_checkup', '体检提醒'),
    ('health_vaccine', '疫苗提醒'),
    ('health_followup', '复诊提醒'),
]

REMINDER_VERBS = {
    'birthday', 'event', 'expiry',
    'health_checkup', 'health_vaccine', 'health_followup',
}


class Notification(models.Model):
    """家庭通知：互动（评论/mention/reaction）+ 系统提醒（生日/事件/文件到期）。"""
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications',
    )
    # 系统提醒时 actor 为空
    actor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications_sent',
        null=True, blank=True,
    )
    verb = models.CharField(max_length=20, choices=VERB_CHOICES)
    moment = models.ForeignKey(
        'feed.Moment', on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications',
    )
    comment = models.ForeignKey(
        'feed.Comment', on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications',
    )
    emoji = models.CharField(max_length=10, blank=True, default='')
    text = models.CharField('预览文字', max_length=200, blank=True, default='')
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # 去重键：同一条提醒同一天只生成一次
    # 格式示例：birthday:2026-06-01:profile:5  event:2026-06-01:event:12  expiry:2026-06-01:file:3
    dedup_key = models.CharField(max_length=100, blank=True, default='', db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '通知'
        verbose_name_plural = '通知'

    def __str__(self):
        return f'{self.verb} -> {self.recipient_id}: {self.text[:40]}'


def notify(recipient, actor, verb, *, moment=None, comment=None, emoji='', text=''):
    """互动通知（评论/mention/reaction）。给自己的不发。返回 Notification 或 None。"""
    if recipient is None or actor is None:
        return None
    if recipient.pk == actor.pk:
        return None
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb=verb,
        moment=moment,
        comment=comment,
        emoji=emoji,
        text=(text or '')[:200],
    )


def notify_reminder(recipient, verb, text, dedup_key):
    """系统提醒通知（无 actor）。同一 dedup_key 今天已存在则跳过。"""
    if Notification.objects.filter(dedup_key=dedup_key, recipient=recipient).exists():
        return None
    return Notification.objects.create(
        recipient=recipient,
        verb=verb,
        text=text[:200],
        dedup_key=dedup_key,
    )
