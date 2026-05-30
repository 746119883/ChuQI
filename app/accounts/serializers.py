from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import Invitation, Profile, ROLE_CHOICES, DEFAULT_INVITATION_TTL


class ProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = (
            'nickname',
            'avatar',
            'avatar_url',
            'display_name',
            'relation',
            'role',
            'birthday',
            'birthday_is_lunar',
        )
        # role 只能通过 admin 专用 endpoint 修改
        read_only_fields = ('role', 'avatar_url', 'display_name')
        extra_kwargs = {
            'avatar': {'write_only': True, 'required': False},
        }

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            url = obj.avatar.url
            return request.build_absolute_uri(url) if request else url
        return None


class UserSerializer(serializers.ModelSerializer):
    """全站通用的用户序列化（嵌入 author/owner/uploader 等地方）。"""
    profile = ProfileSerializer(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'display_name', 'avatar_url', 'profile')

    def get_display_name(self, obj):
        try:
            if obj.profile.nickname:
                return obj.profile.nickname
        except Profile.DoesNotExist:
            pass
        return obj.username

    def get_avatar_url(self, obj):
        try:
            if obj.profile.avatar:
                request = self.context.get('request')
                url = obj.profile.avatar.url
                return request.build_absolute_uri(url) if request else url
        except Profile.DoesNotExist:
            pass
        return None


class MemberSerializer(serializers.ModelSerializer):
    """在 /family/members 中使用，包含 admin 关心的状态。"""
    profile = ProfileSerializer(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    is_superuser = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'display_name', 'avatar_url',
            'is_active', 'is_superuser', 'date_joined', 'profile',
        )
        read_only_fields = ('id', 'username', 'is_superuser', 'date_joined')

    def get_display_name(self, obj):
        try:
            return obj.profile.nickname or obj.username
        except Profile.DoesNotExist:
            return obj.username

    def get_avatar_url(self, obj):
        try:
            if obj.profile.avatar:
                request = self.context.get('request')
                url = obj.profile.avatar.url
                return request.build_absolute_uri(url) if request else url
        except Profile.DoesNotExist:
            pass
        return None


class MemberUpdateSerializer(serializers.Serializer):
    """admin 修改其他成员的角色 / 启用状态。"""
    role = serializers.ChoiceField(choices=ROLE_CHOICES, required=False)
    is_active = serializers.BooleanField(required=False)


class InvitationSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    created_by = UserSerializer(read_only=True)
    used_by = UserSerializer(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    expires_at = serializers.DateTimeField(required=False)

    class Meta:
        model = Invitation
        fields = (
            'id', 'code', 'role', 'role_display',
            'default_nickname', 'note',
            'created_by', 'created_at', 'expires_at',
            'used_by', 'used_at', 'revoked', 'status',
        )
        read_only_fields = (
            'id', 'code', 'created_by', 'created_at',
            'used_by', 'used_at', 'revoked', 'status', 'role_display',
        )

    def create(self, validated_data):
        request = self.context['request']
        if 'expires_at' not in validated_data or not validated_data.get('expires_at'):
            validated_data['expires_at'] = timezone.now() + DEFAULT_INVITATION_TTL
        validated_data['created_by'] = request.user
        validated_data['code'] = Invitation.generate_code()
        return super().create(validated_data)


class RegisterWithCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6)
    username = serializers.CharField(min_length=2, max_length=30)
    password = serializers.CharField(min_length=6, write_only=True)
    nickname = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_code(self, value):
        code = value.strip().upper()
        try:
            invitation = Invitation.objects.get(code=code)
        except Invitation.DoesNotExist:
            raise serializers.ValidationError('邀请码无效')
        if not invitation.is_usable:
            msg = {
                'used': '邀请码已被使用',
                'revoked': '邀请码已撤销',
                'expired': '邀请码已过期',
            }.get(invitation.status, '邀请码不可用')
            raise serializers.ValidationError(msg)
        self.context['invitation'] = invitation
        return code

    def validate_username(self, value):
        username = value.strip()
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError('用户名已存在')
        return username

    def validate_password(self, value):
        validate_password(value)
        return value
