"""每日健康提醒：体检/疫苗/复诊到期与逾期。

建议通过 cron 每日 0 点执行：
    docker exec chuqi-django python manage.py health_send_reminders
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from notifications.models import notify_reminder
from health.models import (
    CheckupPlan,
    HealthReminderSettings,
    MedicalVisit,
    VaccinePlan,
)


def active_recipients():
    return list(User.objects.filter(is_active=True))


def member_name(user):
    try:
        return user.profile.display_name
    except Exception:
        return user.username


class Command(BaseCommand):
    help = '发送健康到期/逾期提醒（体检、疫苗、复诊）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date', dest='date', default=None,
            help='以指定日期(YYYY-MM-DD)为"今天"运行，便于测试；默认系统当天',
        )

    def handle(self, *args, **options):
        today = date.fromisoformat(options['date']) if options.get('date') else date.today()
        recipients = active_recipients()
        cfg = HealthReminderSettings.load()
        total = 0
        # 提前量为 0 表示关闭该类提醒（含到期与逾期）
        if cfg.checkup_lead_days:
            total += self._checkup_reminders(today, recipients, cfg.checkup_lead_days)
        if cfg.vaccine_lead_days:
            total += self._vaccine_reminders(today, recipients, cfg.vaccine_lead_days)
        if cfg.followup_lead_days:
            total += self._followup_reminders(today, recipients, cfg.followup_lead_days)
        self.stdout.write(self.style.SUCCESS(f'health_send_reminders 完成，共创建 {total} 条通知'))

    def _notify_all(self, recipients, verb, text, dedup_key):
        created = 0
        for r in recipients:
            if notify_reminder(r, verb, text, dedup_key):
                created += 1
        return created

    def _checkup_reminders(self, today, recipients, lead_days):
        created = 0
        lead_date = today + timedelta(days=lead_days)
        # dedup_key 不含日期 → 每个阶段(提前/当天/逾期)每个计划只提醒一次，避免每日重发
        for plan in CheckupPlan.objects.filter(status='pending').select_related('user'):
            name = member_name(plan.user)
            if plan.scheduled_date == lead_date:
                text = f'{name} 的 {plan.name} 将于 {plan.scheduled_date} 到期'
                created += self._notify_all(recipients, 'health_checkup', text, f'health_checkup:plan:{plan.id}')
            elif plan.scheduled_date == today:
                text = f'{name} 的 {plan.name} 今天到期'
                created += self._notify_all(recipients, 'health_checkup', text, f'health_checkup_due:plan:{plan.id}')
            elif plan.scheduled_date < today:
                text = f'{name} 的 {plan.name}（{plan.scheduled_date}）已逾期'
                created += self._notify_all(recipients, 'health_checkup', text, f'health_checkup_overdue:plan:{plan.id}')
        return created

    def _vaccine_reminders(self, today, recipients, lead_days):
        created = 0
        lead_date = today + timedelta(days=lead_days)
        for plan in VaccinePlan.objects.filter(status='pending').select_related('user'):
            name = member_name(plan.user)
            dose = f'{plan.vaccine_name} 第{plan.dose_number}剂'
            if plan.scheduled_date == lead_date:
                text = f'{name} 的 {dose}将于 {plan.scheduled_date} 到期'
                created += self._notify_all(recipients, 'health_vaccine', text, f'health_vaccine:plan:{plan.id}')
            elif plan.scheduled_date == today:
                text = f'{name} 的 {dose}今天应接种'
                created += self._notify_all(recipients, 'health_vaccine', text, f'health_vaccine_due:plan:{plan.id}')
            elif plan.scheduled_date < today:
                text = f'{name} 的 {dose}（{plan.scheduled_date}）已逾期，请尽快安排接种'
                created += self._notify_all(recipients, 'health_vaccine', text, f'health_vaccine_overdue:plan:{plan.id}')
        return created

    def _followup_reminders(self, today, recipients, lead_days):
        created = 0
        lead_date = today + timedelta(days=lead_days)
        for visit in MedicalVisit.objects.filter(followup_date=lead_date).select_related('user'):
            name = member_name(visit.user)
            text = f'{name} 的复诊安排将于 {visit.followup_date}，医院：{visit.hospital}'
            dedup = f'health_followup:{today.isoformat()}:visit:{visit.id}'
            created += self._notify_all(recipients, 'health_followup', text, dedup)
        return created
