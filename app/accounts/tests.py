"""账户/家庭权限边界测试。

覆盖最敏感的逻辑:邀请码注册(角色注入)、角色提升、admin 改成员、
自我保护(防自降级/防改 superuser)、防止经 /me 自我提权。
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Invitation


def _set_role(user, role):
    # 信号已建好 profile;直接改缓存实例,避免 user.profile 读到陈旧角色
    user.profile.role = role
    user.profile.save(update_fields=['role'])


class AccountsTestBase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x')
        _set_role(self.admin, 'admin')
        self.member = User.objects.create_user('member', password='x')
        _set_role(self.member, 'member')

    def _invite(self, role='member', **kw):
        return Invitation.objects.create(
            code=Invitation.generate_code(),
            role=role,
            created_by=self.admin,
            expires_at=timezone.now() + timedelta(days=7),
            **kw,
        )


class InvitationPermissionTests(AccountsTestBase):
    def test_member_cannot_create_invitation(self):
        self.client.force_authenticate(self.member)
        resp = self.client.post('/api/family/invitations/', {'role': 'member'})
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_cannot_create_invitation(self):
        resp = self.client.post('/api/family/invitations/', {'role': 'member'})
        self.assertEqual(resp.status_code, 401)

    def test_admin_create_sets_code_and_creator_serverside(self):
        self.client.force_authenticate(self.admin)
        # 即使客户端尝试塞 code/created_by 也应被忽略
        resp = self.client.post('/api/family/invitations/', {
            'role': 'admin', 'code': 'HACKED', 'default_nickname': '爷爷',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertNotEqual(resp.data['code'], 'HACKED')
        self.assertEqual(len(resp.data['code']), 6)
        self.assertEqual(resp.data['created_by']['id'], self.admin.id)
        self.assertEqual(resp.data['role'], 'admin')

    def test_used_invitation_cannot_be_revoked(self):
        inv = self._invite()
        inv.mark_used(self.member)
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(f'/api/family/invitations/{inv.id}/')
        self.assertEqual(resp.status_code, 400)

    def test_delete_unused_soft_revokes(self):
        inv = self._invite()
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(f'/api/family/invitations/{inv.id}/')
        self.assertIn(resp.status_code, (200, 204))
        inv.refresh_from_db()
        self.assertTrue(inv.revoked)  # 软撤销,记录仍在
        self.assertTrue(Invitation.objects.filter(id=inv.id).exists())


class RegisterWithCodeTests(AccountsTestBase):
    def test_register_assigns_invitation_role(self):
        inv = self._invite(role='admin', default_nickname='奶奶')
        resp = self.client.post('/api/auth/register/', {
            'code': inv.code, 'username': 'newgrandma', 'password': 'Chu7-Vault-Pw',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertIn('access', resp.data)
        u = User.objects.get(username='newgrandma')
        self.assertEqual(u.profile.role, 'admin')

    def test_register_ignores_client_supplied_role(self):
        """关键:角色只来自邀请码,客户端 body 里的 role 必须被忽略(防提权)。"""
        inv = self._invite(role='member')
        resp = self.client.post('/api/auth/register/', {
            'code': inv.code, 'username': 'sneaky', 'password': 'Chu7-Vault-Pw',
            'role': 'admin', 'is_superuser': True, 'is_staff': True,
        })
        self.assertEqual(resp.status_code, 201)
        u = User.objects.get(username='sneaky')
        self.assertEqual(u.profile.role, 'member')
        self.assertFalse(u.is_superuser)
        self.assertFalse(u.is_staff)

    def test_register_with_used_code_rejected(self):
        inv = self._invite()
        inv.mark_used(self.member)
        resp = self.client.post('/api/auth/register/', {
            'code': inv.code, 'username': 'x', 'password': 'Chu7-Vault-Pw',
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_with_revoked_code_rejected(self):
        inv = self._invite(revoked=True)
        resp = self.client.post('/api/auth/register/', {
            'code': inv.code, 'username': 'x', 'password': 'Chu7-Vault-Pw',
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_with_expired_code_rejected(self):
        inv = self._invite()
        inv.expires_at = timezone.now() - timedelta(days=1)
        inv.save(update_fields=['expires_at'])
        resp = self.client.post('/api/auth/register/', {
            'code': inv.code, 'username': 'x', 'password': 'Chu7-Vault-Pw',
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_with_invalid_code_rejected(self):
        resp = self.client.post('/api/auth/register/', {
            'code': 'ZZZZZZ', 'username': 'x', 'password': 'Chu7-Vault-Pw',
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_duplicate_username_rejected(self):
        inv = self._invite()
        resp = self.client.post('/api/auth/register/', {
            'code': inv.code, 'username': 'admin', 'password': 'Chu7-Vault-Pw',
        })
        self.assertEqual(resp.status_code, 400)

    def test_code_used_only_once(self):
        inv = self._invite()
        ok = self.client.post('/api/auth/register/', {
            'code': inv.code, 'username': 'first', 'password': 'Chu7-Vault-Pw',
        })
        self.assertEqual(ok.status_code, 201)
        again = self.client.post('/api/auth/register/', {
            'code': inv.code, 'username': 'second', 'password': 'Chu7-Vault-Pw',
        })
        self.assertEqual(again.status_code, 400)


class MemberManagementTests(AccountsTestBase):
    def test_member_cannot_change_roles(self):
        self.client.force_authenticate(self.member)
        resp = self.client.patch(f'/api/family/members/{self.admin.id}/', {'role': 'member'})
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_promote_member(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(f'/api/family/members/{self.member.id}/', {'role': 'admin'})
        self.assertEqual(resp.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.profile.role, 'admin')

    def test_admin_cannot_modify_self(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(f'/api/family/members/{self.admin.id}/', {'role': 'member'})
        self.assertEqual(resp.status_code, 400)

    def test_admin_cannot_modify_superuser(self):
        su = User.objects.create_superuser('root', password='x')
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(f'/api/family/members/{su.id}/', {'is_active': False})
        self.assertEqual(resp.status_code, 400)
        su.refresh_from_db()
        self.assertTrue(su.is_active)

    def test_anonymous_cannot_list_members(self):
        self.assertEqual(self.client.get('/api/family/members/').status_code, 401)


class SelfEscalationTests(AccountsTestBase):
    def test_patch_me_cannot_change_own_role(self):
        """经 /me 改 role 应被忽略(role 是只读字段)。"""
        self.client.force_authenticate(self.member)
        resp = self.client.patch('/api/auth/me/', {'role': 'admin', 'nickname': '小明'})
        self.assertEqual(resp.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.profile.role, 'member')
        self.assertEqual(self.member.profile.nickname, '小明')
