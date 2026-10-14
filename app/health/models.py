from django.contrib.auth.models import User
from django.db import models


class HealthReminderSettings(models.Model):
    """家庭级健康提醒设置（单例）。各提前量：0=关闭，否则 1/3/7/14 天。"""
    vaccine_lead_days = models.PositiveIntegerField('疫苗提醒提前天数', default=3)
    checkup_lead_days = models.PositiveIntegerField('体检提醒提前天数', default=7)
    followup_lead_days = models.PositiveIntegerField('复诊提醒提前天数', default=3)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '健康提醒设置'
        verbose_name_plural = '健康提醒设置'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


BLOOD_TYPE_CHOICES = [
    ('A', 'A'),
    ('B', 'B'),
    ('AB', 'AB'),
    ('O', 'O'),
    ('unknown', '不确定'),
]


class HealthProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='health_profile',
    )
    blood_type = models.CharField(
        '血型', max_length=10, choices=BLOOD_TYPE_CHOICES,
        blank=True, default='',
    )
    # 可变长结构化列表，沿用 recipes 的 JSONField 约定（见 recipes/models.py）
    allergies = models.JSONField(
        '过敏史', default=list, blank=True,
    )  # [{name, type: drug|food|environment, note}]
    chronic_conditions = models.JSONField(
        '慢性病', default=list, blank=True,
    )  # [{name, diagnosed_date, note}]
    medications = models.JSONField(
        '长期用药', default=list, blank=True,
    )  # [{name, dosage, note}]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '健康档案'
        verbose_name_plural = '健康档案'

    def __str__(self):
        return f'{self.user_id} 的健康档案'


def add_months(d, months):
    """日期加 N 个月，溢出当月时回退到该月最后一天。"""
    import calendar
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def age_in_years(birthday, on=None):
    """整岁年龄；birthday 为 None 返回 None。"""
    if not birthday:
        return None
    from datetime import date as _date
    on = on or _date.today()
    return on.year - birthday.year - ((on.month, on.day) < (birthday.month, birthday.day))


# 国家标准儿童体检时间表：(名称, 出生后偏移月数)
CHILD_CHECKUP_SCHEDULE = [
    ('出生体检', 0),
    ('1月龄体检', 1),
    ('3月龄体检', 3),
    ('6月龄体检', 6),
    ('8月龄体检', 8),
    ('12月龄体检', 12),
    ('18月龄体检', 18),
    ('24月龄体检', 24),
    ('30月龄体检', 30),
    ('36月龄体检', 36),
    ('4岁体检', 48),
    ('5岁体检', 60),
    ('6岁体检', 72),
]


CHECKUP_FREQUENCY_CHOICES = [
    ('once', '一次性'),
    ('yearly', '每年'),
    ('every_n_months', '每N个月'),
]

CHECKUP_STATUS_CHOICES = [
    ('pending', '待完成'),
    ('done', '已完成'),
    ('skipped', '跳过'),
]


class CheckupPlan(models.Model):
    """体检计划。"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='checkup_plans',
    )
    name = models.CharField('计划名称', max_length=100)
    scheduled_date = models.DateField('预定日期')
    frequency = models.CharField(
        '频次', max_length=20, choices=CHECKUP_FREQUENCY_CHOICES, default='once',
    )
    interval_months = models.PositiveIntegerField(
        '间隔月数', null=True, blank=True,
    )  # frequency=every_n_months 时使用
    status = models.CharField(
        '状态', max_length=20, choices=CHECKUP_STATUS_CHOICES, default='pending',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date', '-created_at']
        verbose_name = '体检计划'
        verbose_name_plural = '体检计划'

    def __str__(self):
        return f'{self.user_id} - {self.name} @ {self.scheduled_date}'

    def next_date(self):
        """按频次推算下一期日期；一次性返回 None。"""
        if self.frequency == 'yearly':
            return add_months(self.scheduled_date, 12)
        if self.frequency == 'every_n_months' and self.interval_months:
            return add_months(self.scheduled_date, self.interval_months)
        return None


class CheckupResult(models.Model):
    """体检结果，一对一关联体检计划。"""
    plan = models.OneToOneField(
        CheckupPlan, on_delete=models.CASCADE, related_name='result',
    )
    visit_date = models.DateField('就诊日期')
    hospital = models.CharField('医院名称', max_length=100, blank=True, default='')
    items = models.TextField('项目列表', blank=True, default='')
    conclusion = models.TextField('结论', blank=True, default='')
    advice = models.TextField('医生建议', blank=True, default='')
    # [{name, value(float), unit, reference, abnormal(bool)}]
    metrics = models.JSONField('健康指标', default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '体检结果'
        verbose_name_plural = '体检结果'

    def abnormal_count(self):
        return sum(1 for m in (self.metrics or []) if m.get('abnormal'))


ALLOWED_ATTACHMENT_TYPES = {'image/jpeg', 'image/png', 'application/pdf'}
MAX_HEALTH_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def health_attachment_path(instance, filename):
    member_id = instance.owner_id() or 0
    from datetime import date as _date
    return f'health/{member_id}/{_date.today().year}/{filename}'


class HealthAttachment(models.Model):
    """健康模块通用附件（体检结果 / 接种记录 / 就医记录）。"""
    file = models.FileField('文件', upload_to=health_attachment_path)
    name = models.CharField('文件名', max_length=255, blank=True, default='')
    size_bytes = models.PositiveBigIntegerField('大小', default=0)
    content_type = models.CharField('类型', max_length=100, blank=True, default='')
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='health_attachments',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    checkup_result = models.ForeignKey(
        CheckupResult, on_delete=models.CASCADE,
        null=True, blank=True, related_name='attachments',
    )
    vaccination_record = models.ForeignKey(
        'VaccinationRecord', on_delete=models.CASCADE,
        null=True, blank=True, related_name='attachments',
    )
    medical_visit = models.ForeignKey(
        'MedicalVisit', on_delete=models.CASCADE,
        null=True, blank=True, related_name='attachments',
    )

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = '健康附件'
        verbose_name_plural = '健康附件'

    def owner_id(self):
        """附件所属成员 id，用于存储路径。"""
        if self.checkup_result_id:
            return self.checkup_result.plan.user_id
        if self.vaccination_record_id:
            return self.vaccination_record.plan.user_id
        if self.medical_visit_id:
            return self.medical_visit.user_id
        return None

    @property
    def is_image(self):
        return self.content_type in ('image/jpeg', 'image/png')


VACCINE_STATUS_CHOICES = [
    ('pending', '待接种'),
    ('done', '已接种'),
    ('skipped', '跳过'),
]

# 国家免疫规划时间表：(疫苗名称, 剂次, 出生后偏移月数)
CHILD_VACCINE_SCHEDULE = [
    ('乙肝疫苗', 1, 0), ('乙肝疫苗', 2, 1), ('乙肝疫苗', 3, 6),
    ('卡介苗', 1, 0),
    ('脊灰疫苗', 1, 2), ('脊灰疫苗', 2, 3), ('脊灰疫苗', 3, 4), ('脊灰疫苗', 4, 48),
    ('百白破疫苗', 1, 3), ('百白破疫苗', 2, 4), ('百白破疫苗', 3, 5), ('百白破疫苗', 4, 18),
    ('麻腮风疫苗', 1, 8), ('麻腮风疫苗', 2, 18),
    ('乙脑疫苗', 1, 8), ('乙脑疫苗', 2, 24),
    ('A群流脑疫苗', 1, 6), ('A群流脑疫苗', 2, 9),
    ('A+C群流脑疫苗', 1, 36), ('A+C群流脑疫苗', 2, 72),
    ('甲肝疫苗', 1, 18),
]


class VaccinePlan(models.Model):
    """疫苗接种计划（每剂一条）。"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='vaccine_plans',
    )
    vaccine_name = models.CharField('疫苗名称', max_length=100)
    dose_number = models.PositiveIntegerField('剂次', default=1)
    scheduled_date = models.DateField('计划接种日期')
    status = models.CharField(
        '状态', max_length=20, choices=VACCINE_STATUS_CHOICES, default='pending',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date', 'vaccine_name', 'dose_number']
        verbose_name = '疫苗计划'
        verbose_name_plural = '疫苗计划'

    def __str__(self):
        return f'{self.user_id} - {self.vaccine_name} 第{self.dose_number}剂'

    def is_overdue(self):
        from datetime import date as _date
        return self.status == 'pending' and self.scheduled_date < _date.today()


VISIT_TYPE_CHOICES = [
    ('outpatient', '门诊'),
    ('emergency', '急诊'),
    ('inpatient', '住院'),
]


class MedicalVisit(models.Model):
    """就医记录。"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='medical_visits',
    )
    visit_date = models.DateField('就医日期')
    hospital = models.CharField('医院名称', max_length=100, blank=True, default='')
    department = models.CharField('科室', max_length=100, blank=True, default='')
    visit_type = models.CharField(
        '就诊类型', max_length=20, choices=VISIT_TYPE_CHOICES, default='outpatient',
    )
    diagnosis = models.TextField('诊断/主诉', blank=True, default='')
    treatment = models.TextField('处置/用药', blank=True, default='')
    doctor = models.CharField('医生姓名', max_length=50, blank=True, default='')
    followup_date = models.DateField('复诊日期', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-visit_date', '-created_at']
        verbose_name = '就医记录'
        verbose_name_plural = '就医记录'

    def __str__(self):
        return f'{self.user_id} - {self.hospital} @ {self.visit_date}'


class VaccinationRecord(models.Model):
    """接种记录，一对一关联疫苗计划。"""
    plan = models.OneToOneField(
        VaccinePlan, on_delete=models.CASCADE, related_name='record',
    )
    administered_date = models.DateField('实际接种日期')
    location = models.CharField('接种地点', max_length=100, blank=True, default='')
    brand_batch = models.CharField('品牌/批次', max_length=100, blank=True, default='')
    note = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '接种记录'
        verbose_name_plural = '接种记录'
