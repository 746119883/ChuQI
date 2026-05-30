import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


ROLE_CHOICES = [
    ('admin', '家长'),
    ('member', '成员'),
    ('elder', '老人'),
]


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    nickname = models.CharField('昵称', max_length=50, blank=True)
    avatar = models.ImageField('头像', upload_to='avatars/', blank=True, null=True)
    relation = models.CharField('关系', max_length=20, blank=True)
    role = models.CharField('角色', max_length=10, choices=ROLE_CHOICES, default='member')
    birthday = models.DateField('生日', blank=True, null=True)
    birthday_is_lunar = models.BooleanField('农历生日', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '资料'
        verbose_name_plural = '资料'

    def __str__(self):
        return f'{self.user.username} ({self.nickname or "-"})'

    @property
    def display_name(self):
        return self.nickname or self.user.username

    @property
    def is_admin(self):
        return self.role == 'admin' or self.user.is_superuser


# 不会跟 0/O/1/I/L 混的字符集
_INVITE_ALPHABET = ''.join(
    c for c in (string.ascii_uppercase + string.digits)
    if c not in '0O1IL'
)

DEFAULT_INVITATION_TTL = timedelta(days=7)


class Invitation(models.Model):
    code = models.CharField(max_length=6, unique=True, db_index=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    default_nickname = models.CharField(max_length=50, blank=True)
    note = models.CharField('备注', max_length=100, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='invitations_sent',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='invitations_used',
        null=True,
        blank=True,
    )
    used_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '邀请'
        verbose_name_plural = '邀请'

    def __str__(self):
        return f'{self.code} ({self.get_role_display()})'

    @classmethod
    def generate_code(cls):
        while True:
            code = ''.join(secrets.choice(_INVITE_ALPHABET) for _ in range(6))
            if not cls.objects.filter(code=code).exists():
                return code

    @property
    def is_usable(self):
        if self.used_by_id or self.revoked:
            return False
        return timezone.now() < self.expires_at

    @property
    def status(self):
        if self.used_by_id:
            return 'used'
        if self.revoked:
            return 'revoked'
        if timezone.now() >= self.expires_at:
            return 'expired'
        return 'active'

    def mark_used(self, user):
        self.used_by = user
        self.used_at = timezone.now()
        self.save(update_fields=['used_by', 'used_at'])
