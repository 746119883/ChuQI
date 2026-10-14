from datetime import date

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import (
    CheckupPlan,
    HealthAttachment,
    HealthProfile,
    MedicalVisit,
    VaccinePlan,
    add_months,
)


def _make_user(username, role='member'):
    u = User.objects.create_user(username, password='x')
    u.profile.role = role
    u.profile.save(update_fields=['role'])
    return u


class HealthProfileListTests(APITestCase):
    def setUp(self):
        self.member = _make_user('member1')
        self.other = _make_user('member2')

    def test_unauthenticated_returns_401(self):
        resp = self.client.get('/api/health/profiles/')
        self.assertEqual(resp.status_code, 401)

    def test_authenticated_can_list_all_members(self):
        self.client.force_authenticate(self.member)
        resp = self.client.get('/api/health/profiles/')
        self.assertEqual(resp.status_code, 200)
        ids = [item['id'] for item in resp.data]
        self.assertIn(self.member.id, ids)
        self.assertIn(self.other.id, ids)

    def test_list_includes_health_profile(self):
        self.client.force_authenticate(self.member)
        resp = self.client.get('/api/health/profiles/')
        self.assertEqual(resp.status_code, 200)
        for item in resp.data:
            self.assertIn('health_profile', item)


class HealthProfileDetailTests(APITestCase):
    def setUp(self):
        self.member = _make_user('member3')
        self.other = _make_user('member4')

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(f'/api/health/profiles/{self.member.id}/')
        self.assertEqual(resp.status_code, 401)

    def test_get_creates_profile_on_first_access(self):
        self.assertFalse(HealthProfile.objects.filter(user=self.member).exists())
        self.client.force_authenticate(self.other)
        resp = self.client.get(f'/api/health/profiles/{self.member.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(HealthProfile.objects.filter(user=self.member).exists())

    def test_member_can_view_other_member_profile(self):
        self.client.force_authenticate(self.other)
        resp = self.client.get(f'/api/health/profiles/{self.member.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('blood_type', resp.data)

    def test_patch_updates_blood_type(self):
        self.client.force_authenticate(self.member)
        resp = self.client.patch(
            f'/api/health/profiles/{self.member.id}/',
            {'blood_type': 'A'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['blood_type'], 'A')
        self.assertEqual(HealthProfile.objects.get(user=self.member).blood_type, 'A')

    def test_patch_writes_and_reads_back_lists(self):
        self.client.force_authenticate(self.member)
        payload = {
            'allergies': [
                {'name': '青霉素', 'type': 'drug', 'note': '皮疹'},
            ],
            'chronic_conditions': [
                {'name': '高血压', 'diagnosed_date': '2020-01-01', 'note': ''},
            ],
            'medications': [
                {'name': '氨氯地平', 'dosage': '5mg/日', 'note': ''},
            ],
        }
        resp = self.client.patch(
            f'/api/health/profiles/{self.member.id}/', payload, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        # 读回
        resp2 = self.client.get(f'/api/health/profiles/{self.member.id}/')
        self.assertEqual(resp2.data['allergies'][0]['name'], '青霉素')
        self.assertEqual(resp2.data['allergies'][0]['type'], 'drug')
        self.assertEqual(resp2.data['chronic_conditions'][0]['name'], '高血压')
        self.assertEqual(resp2.data['medications'][0]['dosage'], '5mg/日')

    def test_empty_name_rows_filtered(self):
        self.client.force_authenticate(self.member)
        resp = self.client.patch(
            f'/api/health/profiles/{self.member.id}/',
            {'allergies': [
                {'name': '', 'type': 'food', 'note': '空行应被过滤'},
                {'name': '花生', 'type': 'food', 'note': ''},
            ]},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['allergies']), 1)
        self.assertEqual(resp.data['allergies'][0]['name'], '花生')

    def test_invalid_allergy_type_rejected(self):
        self.client.force_authenticate(self.member)
        resp = self.client.patch(
            f'/api/health/profiles/{self.member.id}/',
            {'allergies': [{'name': '某物', 'type': 'bogus'}]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_list_view_stays_brief(self):
        """列表视图不返回明细列表字段，保持轻量。"""
        self.client.force_authenticate(self.member)
        resp = self.client.get('/api/health/profiles/')
        self.assertEqual(resp.status_code, 200)
        for item in resp.data:
            self.assertNotIn('allergies', item['health_profile'])


class CheckupPlanTests(APITestCase):
    def setUp(self):
        self.member = _make_user('chk1')
        self.target = _make_user('chk_target')
        self.client.force_authenticate(self.member)

    def test_create_and_list_checkup(self):
        resp = self.client.post('/api/health/checkups/', {
            'user': self.target.id,
            'name': '年度体检',
            'scheduled_date': '2026-07-01',
            'frequency': 'yearly',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        resp = self.client.get(f'/api/health/checkups/?user_id={self.target.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['name'], '年度体检')

    def test_every_n_months_requires_interval(self):
        resp = self.client.post('/api/health/checkups/', {
            'user': self.target.id,
            'name': '复查',
            'scheduled_date': '2026-07-01',
            'frequency': 'every_n_months',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_complete_yearly_generates_next(self):
        plan = CheckupPlan.objects.create(
            user=self.target, name='年检', scheduled_date=date(2026, 7, 1),
            frequency='yearly',
        )
        resp = self.client.patch(f'/api/health/checkups/{plan.id}/', {
            'status': 'done',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        plans = CheckupPlan.objects.filter(user=self.target).order_by('scheduled_date')
        self.assertEqual(plans.count(), 2)
        self.assertEqual(plans.last().scheduled_date, date(2027, 7, 1))
        self.assertEqual(plans.last().status, 'pending')

    def test_complete_once_no_next(self):
        plan = CheckupPlan.objects.create(
            user=self.target, name='一次性', scheduled_date=date(2026, 7, 1),
            frequency='once',
        )
        self.client.patch(f'/api/health/checkups/{plan.id}/', {'status': 'done'}, format='json')
        self.assertEqual(CheckupPlan.objects.filter(user=self.target).count(), 1)

    def test_complete_twice_no_duplicate_next(self):
        plan = CheckupPlan.objects.create(
            user=self.target, name='年检', scheduled_date=date(2026, 7, 1),
            frequency='yearly', status='done',
        )
        # 已是 done，再 patch 不应再生成
        self.client.patch(f'/api/health/checkups/{plan.id}/', {'status': 'done'}, format='json')
        self.assertEqual(CheckupPlan.objects.filter(user=self.target).count(), 1)

    def test_add_months_overflow(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))


class ChildCheckupScheduleTests(APITestCase):
    def setUp(self):
        self.member = _make_user('sched_member')
        self.child = _make_user('sched_child')
        self.adult = _make_user('sched_adult')
        self.client.force_authenticate(self.member)

    def _set_birthday(self, user, d):
        user.profile.birthday = d
        user.profile.save(update_fields=['birthday'])

    def test_load_generates_13_entries(self):
        self._set_birthday(self.child, date(2024, 1, 1))  # ~2岁
        resp = self.client.post('/api/health/checkups/load-child-schedule/', {
            'user_id': self.child.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['created'], 13)
        self.assertEqual(CheckupPlan.objects.filter(user=self.child).count(), 13)
        # 出生体检日期 = 生日
        born = CheckupPlan.objects.get(user=self.child, name='出生体检')
        self.assertEqual(born.scheduled_date, date(2024, 1, 1))

    def test_reload_only_appends_missing(self):
        self._set_birthday(self.child, date(2024, 1, 1))
        self.client.post('/api/health/checkups/load-child-schedule/', {'user_id': self.child.id}, format='json')
        # 删一条再重载
        CheckupPlan.objects.filter(user=self.child, name='6月龄体检').delete()
        resp = self.client.post('/api/health/checkups/load-child-schedule/', {'user_id': self.child.id}, format='json')
        self.assertEqual(resp.data['created'], 1)
        self.assertEqual(CheckupPlan.objects.filter(user=self.child).count(), 13)

    def test_adult_rejected(self):
        self._set_birthday(self.adult, date(1990, 1, 1))
        resp = self.client.post('/api/health/checkups/load-child-schedule/', {'user_id': self.adult.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_no_birthday_rejected(self):
        resp = self.client.post('/api/health/checkups/load-child-schedule/', {'user_id': self.child.id}, format='json')
        self.assertEqual(resp.status_code, 400)


class CheckupResultTests(APITestCase):
    def setUp(self):
        self.member = _make_user('res_member')
        self.target = _make_user('res_target')
        self.client.force_authenticate(self.member)
        self.plan = CheckupPlan.objects.create(
            user=self.target, name='年检', scheduled_date=date(2026, 7, 1),
        )

    def test_put_result_completes_plan(self):
        resp = self.client.put(f'/api/health/checkups/{self.plan.id}/result/', {
            'visit_date': '2026-07-02',
            'hospital': '市一院',
            'metrics': [
                {'name': '血压-收缩压', 'value': 145, 'unit': 'mmHg', 'abnormal': True},
                {'name': '血压-舒张压', 'value': 85, 'unit': 'mmHg', 'abnormal': False},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'done')

    def test_plan_list_shows_result_summary(self):
        self.client.put(f'/api/health/checkups/{self.plan.id}/result/', {
            'visit_date': '2026-07-02', 'hospital': '市一院',
            'metrics': [{'name': 'X', 'value': 1, 'abnormal': True}],
        }, format='json')
        resp = self.client.get(f'/api/health/checkups/?user_id={self.target.id}')
        summary = resp.data[0]['result_summary']
        self.assertEqual(summary['hospital'], '市一院')
        self.assertEqual(summary['abnormal_count'], 1)

    def test_metric_value_must_be_numeric(self):
        resp = self.client.put(f'/api/health/checkups/{self.plan.id}/result/', {
            'visit_date': '2026-07-02',
            'metrics': [{'name': '血糖', 'value': '高'}],
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_metrics_history(self):
        p2 = CheckupPlan.objects.create(user=self.target, name='年检2', scheduled_date=date(2025, 7, 1))
        self.client.put(f'/api/health/checkups/{self.plan.id}/result/', {
            'visit_date': '2026-07-02',
            'metrics': [{'name': '血压-收缩压', 'value': 145, 'unit': 'mmHg'}],
        }, format='json')
        self.client.put(f'/api/health/checkups/{p2.id}/result/', {
            'visit_date': '2025-07-02',
            'metrics': [{'name': '血压-收缩压', 'value': 130, 'unit': 'mmHg'}],
        }, format='json')
        resp = self.client.get(f'/api/health/metrics-history/?user_id={self.target.id}&name=血压-收缩压')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        # 按 visit_date 升序
        self.assertEqual(resp.data[0]['date'], '2025-07-02')
        self.assertEqual(resp.data[0]['value'], 130)


class HealthAttachmentTests(APITestCase):
    def setUp(self):
        self.member = _make_user('att_member')
        self.target = _make_user('att_target')
        self.client.force_authenticate(self.member)
        self.plan = CheckupPlan.objects.create(
            user=self.target, name='年检', scheduled_date=date(2026, 7, 1),
        )
        from .models import CheckupResult
        self.result = CheckupResult.objects.create(plan=self.plan, visit_date=date(2026, 7, 2))

    def _img(self, name='r.png', content_type='image/png', size=1024):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(name, b'x' * size, content_type=content_type)

    def test_upload_image(self):
        resp = self.client.post('/api/health/attachments/', {
            'file': self._img(), 'checkup_result': self.result.id,
        }, format='multipart')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['is_image'])
        self.assertEqual(resp.data['checkup_result'], self.result.id)

    def test_reject_oversize(self):
        big = self._img(size=21 * 1024 * 1024)
        resp = self.client.post('/api/health/attachments/', {
            'file': big, 'checkup_result': self.result.id,
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_reject_bad_type(self):
        resp = self.client.post('/api/health/attachments/', {
            'file': self._img(name='a.txt', content_type='text/plain'),
            'checkup_result': self.result.id,
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_list_and_delete(self):
        up = self.client.post('/api/health/attachments/', {
            'file': self._img(), 'checkup_result': self.result.id,
        }, format='multipart')
        aid = up.data['id']
        resp = self.client.get(f'/api/health/attachments/?checkup_result={self.result.id}')
        self.assertEqual(len(resp.data), 1)
        d = self.client.delete(f'/api/health/attachments/{aid}/')
        self.assertEqual(d.status_code, 204)
        self.assertEqual(HealthAttachment.objects.count(), 0)


class CheckupReminderTests(APITestCase):
    def setUp(self):
        self.a = _make_user('rem_a')
        self.b = _make_user('rem_b')
        self.target = _make_user('rem_target')

    def _run(self):
        from django.core.management import call_command
        call_command('health_send_reminders')

    def test_upcoming_7_days_notifies_all(self):
        from datetime import timedelta
        from notifications.models import Notification
        CheckupPlan.objects.create(
            user=self.target, name='年检',
            scheduled_date=date.today() + timedelta(days=7), status='pending',
        )
        self._run()
        # 3 个活跃成员各收到一条
        self.assertEqual(Notification.objects.filter(verb='health_checkup').count(), 3)

    def test_overdue_notifies(self):
        from datetime import timedelta
        from notifications.models import Notification
        CheckupPlan.objects.create(
            user=self.target, name='年检',
            scheduled_date=date.today() - timedelta(days=2), status='pending',
        )
        self._run()
        self.assertEqual(Notification.objects.filter(verb='health_checkup').count(), 3)
        self.assertIn('逾期', Notification.objects.filter(verb='health_checkup').first().text)

    def test_idempotent_same_day(self):
        from datetime import timedelta
        from notifications.models import Notification
        CheckupPlan.objects.create(
            user=self.target, name='年检',
            scheduled_date=date.today() + timedelta(days=7), status='pending',
        )
        self._run()
        self._run()
        self.assertEqual(Notification.objects.filter(verb='health_checkup').count(), 3)

    def test_not_due_no_notification(self):
        from datetime import timedelta
        from notifications.models import Notification
        CheckupPlan.objects.create(
            user=self.target, name='年检',
            scheduled_date=date.today() + timedelta(days=30), status='pending',
        )
        self._run()
        self.assertEqual(Notification.objects.filter(verb='health_checkup').count(), 0)

    def test_due_today_notifies(self):
        from notifications.models import Notification
        CheckupPlan.objects.create(
            user=self.target, name='年检', scheduled_date=date.today(), status='pending',
        )
        self._run()
        notes = Notification.objects.filter(verb='health_checkup')
        self.assertEqual(notes.count(), 3)
        self.assertIn('今天到期', notes.first().text)

    def test_overdue_only_once_across_days(self):
        """逾期提醒跨天只发一次（不再每天重发）。"""
        from django.core.management import call_command
        from notifications.models import Notification
        # 计划日期 2026-06-01；分别以 06-02、06-03 为"今天"运行
        CheckupPlan.objects.create(
            user=self.target, name='年检', scheduled_date=date(2026, 6, 1), status='pending',
        )
        call_command('health_send_reminders', date='2026-06-02')
        call_command('health_send_reminders', date='2026-06-03')
        # 3 个成员各一条逾期，跨两天仍只 3 条
        self.assertEqual(Notification.objects.filter(verb='health_checkup').count(), 3)

    def test_full_lifecycle_due_then_overdue(self):
        """到期当天 1 条 + 逾期当天(次日)1 条，共 2 轮（每成员 2 条）。"""
        from django.core.management import call_command
        from notifications.models import Notification
        CheckupPlan.objects.create(
            user=self.target, name='年检', scheduled_date=date(2026, 6, 1), status='pending',
        )
        call_command('health_send_reminders', date='2026-06-01')  # 到期当天
        call_command('health_send_reminders', date='2026-06-02')  # 逾期次日
        call_command('health_send_reminders', date='2026-06-03')  # 再逾期，不应重发
        # 每成员 2 条(到期+逾期各一次)，3 成员 = 6
        self.assertEqual(Notification.objects.filter(verb='health_checkup').count(), 6)


class VaccinePlanTests(APITestCase):
    def setUp(self):
        self.member = _make_user('vac_member')
        self.target = _make_user('vac_target')
        self.client.force_authenticate(self.member)

    def test_create_and_list(self):
        resp = self.client.post('/api/health/vaccines/', {
            'user': self.target.id, 'vaccine_name': '乙肝疫苗',
            'dose_number': 1, 'scheduled_date': '2026-08-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        resp = self.client.get(f'/api/health/vaccines/?user_id={self.target.id}')
        self.assertEqual(len(resp.data), 1)

    def test_overdue_flag(self):
        from datetime import timedelta
        VaccinePlan.objects.create(
            user=self.target, vaccine_name='脊灰', dose_number=1,
            scheduled_date=date.today() - timedelta(days=1), status='pending',
        )
        resp = self.client.get(f'/api/health/vaccines/?user_id={self.target.id}')
        self.assertTrue(resp.data[0]['is_overdue'])

    def test_overview_groups(self):
        from datetime import timedelta
        VaccinePlan.objects.create(user=self.target, vaccine_name='A', dose_number=1,
            scheduled_date=date.today() + timedelta(days=10), status='pending')
        VaccinePlan.objects.create(user=self.target, vaccine_name='B', dose_number=1,
            scheduled_date=date.today() - timedelta(days=10), status='pending')
        VaccinePlan.objects.create(user=self.target, vaccine_name='C', dose_number=1,
            scheduled_date=date.today(), status='done')
        resp = self.client.get(f'/api/health/vaccines/overview/?user_id={self.target.id}')
        self.assertEqual(len(resp.data['pending']), 1)
        self.assertEqual(len(resp.data['overdue']), 1)
        self.assertEqual(len(resp.data['done']), 1)


class ChildVaccineScheduleTests(APITestCase):
    def setUp(self):
        self.member = _make_user('vs_member')
        self.child = _make_user('vs_child')
        self.adult = _make_user('vs_adult')
        self.client.force_authenticate(self.member)

    def _bd(self, user, d):
        user.profile.birthday = d
        user.profile.save(update_fields=['birthday'])

    def test_load_generates_full_schedule(self):
        from .models import CHILD_VACCINE_SCHEDULE
        self._bd(self.child, date(2024, 1, 1))
        resp = self.client.post('/api/health/vaccines/load-child-schedule/', {'user_id': self.child.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['created'], len(CHILD_VACCINE_SCHEDULE))
        # 乙肝第1剂 = 出生日
        hep = VaccinePlan.objects.get(user=self.child, vaccine_name='乙肝疫苗', dose_number=1)
        self.assertEqual(hep.scheduled_date, date(2024, 1, 1))

    def test_reload_only_appends_missing_doses(self):
        self._bd(self.child, date(2024, 1, 1))
        self.client.post('/api/health/vaccines/load-child-schedule/', {'user_id': self.child.id}, format='json')
        VaccinePlan.objects.filter(user=self.child, vaccine_name='卡介苗', dose_number=1).delete()
        resp = self.client.post('/api/health/vaccines/load-child-schedule/', {'user_id': self.child.id}, format='json')
        self.assertEqual(resp.data['created'], 1)

    def test_adult_rejected(self):
        self._bd(self.adult, date(1990, 1, 1))
        resp = self.client.post('/api/health/vaccines/load-child-schedule/', {'user_id': self.adult.id}, format='json')
        self.assertEqual(resp.status_code, 400)


class VaccinationRecordTests(APITestCase):
    def setUp(self):
        self.member = _make_user('vr_member')
        self.target = _make_user('vr_target')
        self.client.force_authenticate(self.member)
        self.plan = VaccinePlan.objects.create(
            user=self.target, vaccine_name='乙肝疫苗', dose_number=1,
            scheduled_date=date(2026, 8, 1), status='pending',
        )

    def test_put_record_marks_done(self):
        resp = self.client.put(f'/api/health/vaccines/{self.plan.id}/record/', {
            'administered_date': '2026-08-02', 'location': '社区卫生中心',
            'brand_batch': '批次X',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'done')

    def test_upload_record_image(self):
        from .models import VaccinationRecord
        from django.core.files.uploadedfile import SimpleUploadedFile
        rec = VaccinationRecord.objects.create(plan=self.plan, administered_date=date(2026, 8, 2))
        img = SimpleUploadedFile('y.png', b'x' * 100, content_type='image/png')
        resp = self.client.post('/api/health/attachments/', {
            'file': img, 'vaccination_record': rec.id,
        }, format='multipart')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['vaccination_record'], rec.id)
        lst = self.client.get(f'/api/health/attachments/?vaccination_record={rec.id}')
        self.assertEqual(len(lst.data), 1)


class VaccineReminderTests(APITestCase):
    def setUp(self):
        self.a = _make_user('vrem_a')
        self.b = _make_user('vrem_b')
        self.target = _make_user('vrem_target')

    def _run(self):
        from django.core.management import call_command
        call_command('health_send_reminders')

    def test_upcoming_3_days_notifies_all(self):
        from datetime import timedelta
        from notifications.models import Notification
        VaccinePlan.objects.create(
            user=self.target, vaccine_name='乙肝疫苗', dose_number=1,
            scheduled_date=date.today() + timedelta(days=3), status='pending',
        )
        self._run()
        notes = Notification.objects.filter(verb='health_vaccine')
        self.assertEqual(notes.count(), 3)
        self.assertIn('第1剂', notes.first().text)

    def test_overdue_vaccine(self):
        from datetime import timedelta
        from notifications.models import Notification
        VaccinePlan.objects.create(
            user=self.target, vaccine_name='脊灰疫苗', dose_number=2,
            scheduled_date=date.today() - timedelta(days=5), status='pending',
        )
        self._run()
        notes = Notification.objects.filter(verb='health_vaccine')
        self.assertEqual(notes.count(), 3)
        self.assertIn('逾期', notes.first().text)

    def test_idempotent(self):
        from datetime import timedelta
        from notifications.models import Notification
        VaccinePlan.objects.create(
            user=self.target, vaccine_name='乙肝疫苗', dose_number=1,
            scheduled_date=date.today() + timedelta(days=3), status='pending',
        )
        self._run()
        self._run()
        self.assertEqual(Notification.objects.filter(verb='health_vaccine').count(), 3)

    def test_due_today_notifies(self):
        from notifications.models import Notification
        VaccinePlan.objects.create(
            user=self.target, vaccine_name='乙肝疫苗', dose_number=1,
            scheduled_date=date.today(), status='pending',
        )
        self._run()
        notes = Notification.objects.filter(verb='health_vaccine')
        self.assertEqual(notes.count(), 3)
        self.assertIn('今天应接种', notes.first().text)

    def test_overdue_only_once_across_days(self):
        from django.core.management import call_command
        from notifications.models import Notification
        VaccinePlan.objects.create(
            user=self.target, vaccine_name='脊灰疫苗', dose_number=2,
            scheduled_date=date(2026, 6, 1), status='pending',
        )
        call_command('health_send_reminders', date='2026-06-05')
        call_command('health_send_reminders', date='2026-06-06')
        self.assertEqual(Notification.objects.filter(verb='health_vaccine').count(), 3)


class MedicalVisitTests(APITestCase):
    def setUp(self):
        self.member = _make_user('mv_member')
        self.target = _make_user('mv_target')
        self.client.force_authenticate(self.member)

    def test_create_and_list_desc(self):
        self.client.post('/api/health/visits/', {
            'user': self.target.id, 'visit_date': '2026-01-01', 'hospital': 'A院',
            'visit_type': 'outpatient',
        }, format='json')
        self.client.post('/api/health/visits/', {
            'user': self.target.id, 'visit_date': '2026-05-01', 'hospital': 'B院',
            'visit_type': 'emergency',
        }, format='json')
        resp = self.client.get(f'/api/health/visits/?user_id={self.target.id}')
        self.assertEqual(len(resp.data), 2)
        # 时间倒序：最新在前
        self.assertEqual(resp.data[0]['hospital'], 'B院')

    def test_edit_visit(self):
        c = self.client.post('/api/health/visits/', {
            'user': self.target.id, 'visit_date': '2026-01-01', 'hospital': 'A院',
        }, format='json')
        vid = c.data['id']
        resp = self.client.patch(f'/api/health/visits/{vid}/', {'department': '内科'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['department'], '内科')

    def test_upload_visit_attachment(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        v = MedicalVisit.objects.create(user=self.target, visit_date=date(2026, 1, 1))
        pdf = SimpleUploadedFile('r.pdf', b'%PDF-1.4 x', content_type='application/pdf')
        resp = self.client.post('/api/health/attachments/', {
            'file': pdf, 'medical_visit': v.id,
        }, format='multipart')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['medical_visit'], v.id)
        self.assertFalse(resp.data['is_image'])
        lst = self.client.get(f'/api/health/attachments/?medical_visit={v.id}')
        self.assertEqual(len(lst.data), 1)


class FollowupReminderTests(APITestCase):
    def setUp(self):
        self.a = _make_user('frem_a')
        self.b = _make_user('frem_b')
        self.target = _make_user('frem_target')

    def _run(self):
        from django.core.management import call_command
        call_command('health_send_reminders')

    def test_followup_3_days_notifies_all(self):
        from datetime import timedelta
        from notifications.models import Notification
        MedicalVisit.objects.create(
            user=self.target, visit_date=date.today(), hospital='市一院',
            followup_date=date.today() + timedelta(days=3),
        )
        self._run()
        notes = Notification.objects.filter(verb='health_followup')
        self.assertEqual(notes.count(), 3)
        self.assertIn('复诊', notes.first().text)
        self.assertIn('市一院', notes.first().text)

    def test_no_followup_no_notification(self):
        from notifications.models import Notification
        MedicalVisit.objects.create(user=self.target, visit_date=date.today(), hospital='X')
        self._run()
        self.assertEqual(Notification.objects.filter(verb='health_followup').count(), 0)

    def test_idempotent(self):
        from datetime import timedelta
        from notifications.models import Notification
        MedicalVisit.objects.create(
            user=self.target, visit_date=date.today(), hospital='市一院',
            followup_date=date.today() + timedelta(days=3),
        )
        self._run()
        self._run()
        self.assertEqual(Notification.objects.filter(verb='health_followup').count(), 3)


class ReminderSettingsTests(APITestCase):
    def setUp(self):
        self.member = _make_user('set_member')
        self.target = _make_user('set_target')
        self.client.force_authenticate(self.member)

    def test_get_defaults(self):
        resp = self.client.get('/api/health/reminder-settings/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['checkup_lead_days'], 7)
        self.assertEqual(resp.data['vaccine_lead_days'], 3)

    def test_put_updates(self):
        resp = self.client.put('/api/health/reminder-settings/', {'vaccine_lead_days': 14}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['vaccine_lead_days'], 14)

    def test_invalid_lead_rejected(self):
        resp = self.client.put('/api/health/reminder-settings/', {'vaccine_lead_days': 5}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_custom_lead_changes_trigger(self):
        from datetime import timedelta
        from notifications.models import Notification
        from django.core.management import call_command
        # 设疫苗提前量为 14 天
        self.client.put('/api/health/reminder-settings/', {'vaccine_lead_days': 14}, format='json')
        VaccinePlan.objects.create(
            user=self.target, vaccine_name='乙肝疫苗', dose_number=1,
            scheduled_date=date.today() + timedelta(days=14), status='pending',
        )
        call_command('health_send_reminders')
        self.assertEqual(Notification.objects.filter(verb='health_vaccine').count(), 2)

    def test_closed_disables(self):
        from datetime import timedelta
        from notifications.models import Notification
        from django.core.management import call_command
        # 关闭体检提醒
        self.client.put('/api/health/reminder-settings/', {'checkup_lead_days': 0}, format='json')
        CheckupPlan.objects.create(
            user=self.target, name='年检',
            scheduled_date=date.today() - timedelta(days=2), status='pending',
        )
        call_command('health_send_reminders')
        self.assertEqual(Notification.objects.filter(verb='health_checkup').count(), 0)
