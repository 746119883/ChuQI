"""文件柜权限边界测试:可见性隔离 + owner 写保护 + shared 过滤。

这些是隐私敏感逻辑(家庭证件/账单),改错会导致越权可见或越权修改,
故重点覆盖。
"""
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from .models import Folder, File


def _upload(name='a.txt', content=b'hello'):
    return SimpleUploadedFile(name, content, content_type='text/plain')


class VaultTestBase(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')

    def _file(self, uploader, visibility='family', name='doc.txt', folder=None):
        return File.objects.create(
            uploader=uploader, visibility=visibility, name=name,
            file=_upload(name), size_bytes=5, folder=folder,
        )

    def _folder(self, owner, visibility='family', name='证件'):
        return Folder.objects.create(owner=owner, visibility=visibility, name=name)


class FileVisibilityTests(VaultTestBase):
    def test_default_lists_only_own_files(self):
        """默认(无 shared):只看自己上传的,无论可见性。"""
        self._file(self.alice, 'family', 'alice家庭.txt')
        self._file(self.alice, 'private', 'alice私密.txt')
        self._file(self.bob, 'family', 'bob家庭.txt')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/vault/files/')
        self.assertEqual(resp.status_code, 200)
        names = {f['name'] for f in resp.data}
        self.assertEqual(names, {'alice家庭.txt', 'alice私密.txt'})

    def test_shared_lists_only_family_visibility(self):
        """shared=1:只看 family 可见的(含别人的),不含任何 private。"""
        self._file(self.alice, 'family', 'alice家庭.txt')
        self._file(self.alice, 'private', 'alice私密.txt')
        self._file(self.bob, 'family', 'bob家庭.txt')
        self._file(self.bob, 'private', 'bob私密.txt')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/vault/files/?shared=1')
        names = {f['name'] for f in resp.data}
        self.assertEqual(names, {'alice家庭.txt', 'bob家庭.txt'})

    def test_other_user_private_file_not_retrievable(self):
        """直接访问他人 private 文件详情应 404(被 queryset 挡掉)。"""
        f = self._file(self.bob, 'private', 'bob私密.txt')
        self.client.force_authenticate(self.alice)
        resp = self.client.get(f'/api/vault/files/{f.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_family_file_of_others_needs_shared_flag(self):
        """他人 family 文件:默认入口看不到,共享空间(shared=1)可见。"""
        f = self._file(self.bob, 'family', 'bob家庭.txt')
        self.client.force_authenticate(self.alice)
        # 默认入口(我的文件柜)看不到别人的
        self.assertEqual(self.client.get(f'/api/vault/files/{f.id}/').status_code, 404)
        # 共享空间能看到
        resp = self.client.get(f'/api/vault/files/{f.id}/?shared=1')
        self.assertEqual(resp.status_code, 200)


class FileWriteProtectionTests(VaultTestBase):
    def test_non_owner_cannot_update_family_file(self):
        """family 文件别人能看,但不能改。"""
        f = self._file(self.bob, 'family', 'bob家庭.txt')
        self.client.force_authenticate(self.alice)
        resp = self.client.patch(f'/api/vault/files/{f.id}/', {'name': '改名'})
        self.assertIn(resp.status_code, (403, 404))
        f.refresh_from_db()
        self.assertEqual(f.name, 'bob家庭.txt')

    def test_non_owner_cannot_delete_family_file(self):
        f = self._file(self.bob, 'family', 'bob家庭.txt')
        self.client.force_authenticate(self.alice)
        resp = self.client.delete(f'/api/vault/files/{f.id}/')
        self.assertIn(resp.status_code, (403, 404))
        self.assertTrue(File.objects.filter(id=f.id).exists())

    def test_owner_can_update_own_file(self):
        f = self._file(self.alice, 'family', 'alice家庭.txt')
        self.client.force_authenticate(self.alice)
        resp = self.client.patch(f'/api/vault/files/{f.id}/', {'name': '新名'})
        self.assertEqual(resp.status_code, 200)
        f.refresh_from_db()
        self.assertEqual(f.name, '新名')

    def test_non_owner_cannot_move_file(self):
        f = self._file(self.bob, 'family', 'bob家庭.txt')
        dest = self._folder(self.alice, name='alice目录')
        self.client.force_authenticate(self.alice)
        resp = self.client.post(f'/api/vault/files/{f.id}/move/', {'folder_id': dest.id})
        self.assertIn(resp.status_code, (403, 404))
        f.refresh_from_db()
        self.assertIsNone(f.folder_id)


class FolderVisibilityTests(VaultTestBase):
    def test_default_lists_only_own_folders(self):
        self._folder(self.alice, 'family', 'alice家庭夹')
        self._folder(self.alice, 'private', 'alice私密夹')
        self._folder(self.bob, 'family', 'bob家庭夹')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/vault/folders/')
        names = {f['name'] for f in resp.data}
        self.assertEqual(names, {'alice家庭夹', 'alice私密夹'})

    def test_shared_lists_only_family_folders(self):
        self._folder(self.alice, 'family', 'alice家庭夹')
        self._folder(self.alice, 'private', 'alice私密夹')
        self._folder(self.bob, 'family', 'bob家庭夹')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/vault/folders/?shared=1')
        names = {f['name'] for f in resp.data}
        self.assertEqual(names, {'alice家庭夹', 'bob家庭夹'})

    def test_other_user_private_folder_not_retrievable(self):
        fo = self._folder(self.bob, 'private', 'bob私密夹')
        self.client.force_authenticate(self.alice)
        resp = self.client.get(f'/api/vault/folders/{fo.id}/')
        self.assertEqual(resp.status_code, 404)


class FileUploadTests(VaultTestBase):
    def test_upload_success_sets_uploader(self):
        f = SimpleUploadedFile('a.bin', b'x' * 10, content_type='application/octet-stream')
        self.client.force_authenticate(self.alice)
        resp = self.client.post('/api/vault/files/upload/', {'files': f}, format='multipart')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['created'][0]['uploader']['id'], self.alice.id)

    def test_upload_requires_files(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.post('/api/vault/files/upload/', {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_blocked(self):
        resp = self.client.get('/api/vault/files/')
        self.assertEqual(resp.status_code, 401)
