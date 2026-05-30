from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Invitation, Profile
from .permissions import IsFamilyAdmin, IsFamilyMember
from .serializers import (
    InvitationSerializer,
    MemberSerializer,
    MemberUpdateSerializer,
    ProfileSerializer,
    RegisterWithCodeSerializer,
    UserSerializer,
)


class MeView(APIView):
    """GET / PATCH 当前登录用户的资料。"""
    permission_classes = [IsFamilyMember]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        return Response(UserSerializer(request.user, context={'request': request}).data)

    def patch(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = ProfileSerializer(
            profile, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user, context={'request': request}).data)


class MembersView(APIView):
    permission_classes = [IsFamilyMember]

    def get(self, request):
        # 列出所有"有 profile"的用户。superuser 也算成员。
        qs = User.objects.select_related('profile').order_by('-is_active', 'date_joined')
        return Response(
            MemberSerializer(qs, many=True, context={'request': request}).data
        )


class MemberDetailView(APIView):
    """admin 修改成员（角色 / 启用）。"""
    permission_classes = [IsFamilyAdmin]

    def patch(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        # 永远不能改 superuser 的角色或停用 superuser
        if target.is_superuser and (
            'role' in request.data or 'is_active' in request.data
        ):
            return Response(
                {'detail': '不能修改超级用户'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # 不能自己改自己（防止误把自己降级或停用）
        if target.pk == request.user.pk:
            return Response(
                {'detail': '不能修改自己的角色或状态，请使用 /me'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = MemberUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'is_active' in data:
            target.is_active = data['is_active']
            target.save(update_fields=['is_active'])

        if 'role' in data:
            profile, _ = Profile.objects.get_or_create(user=target)
            profile.role = data['role']
            profile.save(update_fields=['role'])

        return Response(
            MemberSerializer(target, context={'request': request}).data
        )


class InvitationViewSet(viewsets.ModelViewSet):
    serializer_class = InvitationSerializer
    permission_classes = [IsFamilyAdmin]
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        return Invitation.objects.select_related('created_by', 'used_by').all()

    def perform_destroy(self, instance):
        # 撤销而非删除，留审计痕迹
        if instance.used_by_id:
            # 已使用的不允许撤销/删除
            from rest_framework.exceptions import ValidationError
            raise ValidationError('邀请已被使用，无法撤销')
        instance.revoked = True
        instance.save(update_fields=['revoked'])


@api_view(['POST'])
@permission_classes([AllowAny])
def register_with_code(request):
    """凭邀请码注册 + 直接返回 JWT。"""
    serializer = RegisterWithCodeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    invitation = serializer.context['invitation']
    username = serializer.validated_data['username']
    password = serializer.validated_data['password']
    nickname = (
        serializer.validated_data.get('nickname', '').strip()
        or invitation.default_nickname
    )

    user = User.objects.create_user(username=username, password=password)
    # signals.ensure_profile 已经建好 Profile(role=member)
    profile = user.profile
    profile.role = invitation.role
    if nickname:
        profile.nickname = nickname
    profile.save()

    invitation.mark_used(user)

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user, context={'request': request}).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def invitation_lookup(request, code):
    """注册页用：根据 code 查邀请信息，告知前端预填昵称/角色。"""
    try:
        invitation = Invitation.objects.get(code=code.upper())
    except Invitation.DoesNotExist:
        return Response({'detail': '邀请码无效'}, status=status.HTTP_404_NOT_FOUND)
    if not invitation.is_usable:
        msg = {
            'used': '邀请码已被使用',
            'revoked': '邀请码已撤销',
            'expired': '邀请码已过期',
        }.get(invitation.status, '邀请码不可用')
        return Response(
            {'detail': msg, 'status': invitation.status},
            status=status.HTTP_410_GONE,
        )
    return Response({
        'code': invitation.code,
        'role': invitation.role,
        'role_display': invitation.get_role_display(),
        'default_nickname': invitation.default_nickname,
        'note': invitation.note,
        'invited_by': invitation.created_by.username,
    })
