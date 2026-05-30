"""
提醒扫描逻辑。被 check_reminders API 调用。
覆盖三类：① 生日  ② 日历事件  ③ 文件到期
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db.models import Q

from .models import notify_reminder

# 默认提前提醒天数（事件未设置 remind_days_before 时使用）
DEFAULT_REMIND_DAYS = 3


def _today():
    return date.today()


# ── 农历 ─────────────────────────────────────────────────────────────────────

def _lunar_to_solar(year: int, month: int, day: int) -> date | None:
    """农历转公历，失败返回 None。"""
    try:
        from lunardate import LunarDate
        return LunarDate(year, month, day).toSolarDate()
    except Exception:
        return None


def _next_solar_date(month: int, day: int, is_lunar: bool, base: date) -> date | None:
    """计算 month/day（公历或农历）在今年或明年最近的一次公历日期。"""
    for year in (base.year, base.year + 1):
        if is_lunar:
            d = _lunar_to_solar(year, month, day)
        else:
            try:
                d = date(year, month, day)
            except ValueError:
                d = None
        if d and d >= base:
            return d
    return None


# ── 各类扫描 ─────────────────────────────────────────────────────────────────

def scan_birthdays(recipients: list[User]) -> int:
    """给所有有生日的成员，向全家人发提醒。返回新建通知数。"""
    from accounts.models import Profile

    today = _today()
    created = 0
    profiles = Profile.objects.exclude(birthday__isnull=True).select_related('user')

    for profile in profiles:
        bd = profile.birthday
        next_date = _next_solar_date(bd.month, bd.day, profile.birthday_is_lunar, today)
        if next_date is None:
            continue
        days_left = (next_date - today).days
        if days_left > DEFAULT_REMIND_DAYS:
            continue

        name = profile.display_name
        if days_left == 0:
            text = f'🎂 今天是 {name} 的生日！'
        elif days_left == 1:
            text = f'🎂 明天是 {name} 的生日'
        else:
            text = f'🎂 {name} 的生日还有 {days_left} 天（{next_date.strftime("%m月%d日")}）'

        dedup_date = today.isoformat()
        for user in recipients:
            key = f'birthday:{dedup_date}:profile:{profile.pk}'
            n = notify_reminder(user, 'birthday', text, key)
            if n:
                created += 1
    return created


def scan_events(recipients: list[User]) -> int:
    """扫描日历事件，按 remind_days_before 提前提醒。"""
    from events.models import Event

    today = _today()
    created = 0
    events = Event.objects.filter(
        remind_days_before__isnull=False,
        visibility='family',
    )

    for ev in events:
        remind_days = ev.remind_days_before or DEFAULT_REMIND_DAYS
        next_date = _next_solar_date(ev.date_month, ev.date_day, ev.is_lunar, today)
        if next_date is None:
            continue
        days_left = (next_date - today).days
        if days_left > remind_days or days_left < 0:
            continue

        if days_left == 0:
            text = f'📅 今天：{ev.title}'
        elif days_left == 1:
            text = f'📅 明天：{ev.title}'
        else:
            text = f'📅 {ev.title} 还有 {days_left} 天（{next_date.strftime("%m月%d日")}）'

        dedup_date = today.isoformat()
        for user in recipients:
            key = f'event:{dedup_date}:event:{ev.pk}'
            n = notify_reminder(user, 'event', text, key)
            if n:
                created += 1
    return created


def scan_expiry(user: User) -> int:
    """扫描该用户有权看的文件，到期前 DEFAULT_REMIND_DAYS 天提醒。"""
    from vault.models import File

    today = _today()
    warn_before = today + timedelta(days=DEFAULT_REMIND_DAYS)
    created = 0

    files = File.objects.filter(
        expires_at__isnull=False,
        expires_at__lte=warn_before,
        expires_at__gte=today,
    ).filter(Q(uploader=user) | Q(visibility='family'))

    for f in files:
        days_left = (f.expires_at - today).days
        if days_left == 0:
            text = f'📄 文件「{f.name}」今天到期'
        elif days_left == 1:
            text = f'📄 文件「{f.name}」明天到期'
        else:
            text = f'📄 文件「{f.name}」还有 {days_left} 天到期'

        key = f'expiry:{today.isoformat()}:file:{f.pk}'
        n = notify_reminder(user, 'expiry', text, key)
        if n:
            created += 1
    return created


# ── 入口 ─────────────────────────────────────────────────────────────────────

def run_reminders_for_user(user: User) -> dict:
    """对登录用户触发一次全量扫描，返回新建通知数汇总。"""
    from django.contrib.auth.models import User as UserModel
    # 家庭所有活跃成员（生日/事件提醒要发给全家）
    all_users = list(UserModel.objects.filter(is_active=True))

    b = scan_birthdays(all_users)
    e = scan_events(all_users)
    x = scan_expiry(user)
    return {'birthday': b, 'event': e, 'expiry': x, 'total': b + e + x}
