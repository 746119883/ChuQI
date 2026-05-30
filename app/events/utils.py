"""事件展开:把 Event 模板按公历/农历 + 是否每年重复,扩展成具体日期的 occurrences。"""
from datetime import date, timedelta
from lunardate import LunarDate


def event_occurrences_in_range(event, start: date, end: date):
    """生成 event 在 [start, end] 内的所有公历发生日期 (含两端)。

    返回 list of date 对象。
    """
    out = []
    if event.yearly_recurring:
        years = range(start.year, end.year + 1)
    else:
        if not event.date_year:
            return out
        years = [event.date_year]

    for y in years:
        actual = _compute_gregorian(event, y)
        if actual is None:
            continue
        if start <= actual <= end:
            out.append(actual)
    return out


def _compute_gregorian(event, year: int):
    """根据 event 的设置算出在指定年份的公历日期。无效返回 None。"""
    try:
        if event.is_lunar:
            lunar = LunarDate(year, event.date_month, event.date_day)
            sd = lunar.toSolarDate()
            return date(sd.year, sd.month, sd.day)
        return date(year, event.date_month, event.date_day)
    except (ValueError, OverflowError):
        return None


def gregorian_to_lunar_str(d: date) -> str:
    """公历日期 -> 农历字符串,比如 '农历四月廿三'。"""
    try:
        lunar = LunarDate.fromSolarDate(d.year, d.month, d.day)
        return f'{_CN_MONTH[lunar.month - 1]}{_CN_DAY[lunar.day - 1]}'
    except Exception:
        return ''


_CN_MONTH = ['正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '冬月', '腊月']

# 农历日期的中文写法:初一/初二/.../三十
_CN_DAY = [
    '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
    '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
    '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十',
]


def expand_for_upcoming(events, days: int = 60):
    """近 N 天内的事件 occurrences,按日期升序返回。"""
    today = date.today()
    end = today + timedelta(days=days)
    rows = []
    for ev in events:
        for d in event_occurrences_in_range(ev, today, end):
            rows.append((d, ev))
    rows.sort(key=lambda r: r[0])
    return rows


def expand_for_range(events, start: date, end: date):
    """[start, end] 内所有 occurrences,按日期升序返回。"""
    rows = []
    for ev in events:
        for d in event_occurrences_in_range(ev, start, end):
            rows.append((d, ev))
    rows.sort(key=lambda r: r[0])
    return rows


class _SyntheticBirthday:
    """让 Profile 生日复用 event_occurrences_in_range —— 只需 quack 出这几个属性。"""
    def __init__(self, birthday, is_lunar):
        self.yearly_recurring = True
        self.date_year = birthday.year
        self.date_month = birthday.month
        self.date_day = birthday.day
        self.is_lunar = is_lunar


def profile_birthday_occurrences(profiles, start: date, end: date):
    """根据家庭成员资料里的生日，生成 [start, end] 内的 occurrences。

    profiles: 可迭代的 Profile（需带 .user / .birthday / .birthday_is_lunar）。
    返回 list of (date, profile)。
    """
    rows = []
    for profile in profiles:
        if not profile.birthday:
            continue
        synth = _SyntheticBirthday(profile.birthday, profile.birthday_is_lunar)
        for d in event_occurrences_in_range(synth, start, end):
            rows.append((d, profile))
    return rows
