# -*- coding:utf-8 -*-
"""OPT-P0-22：停用用户同名覆盖启用 — B1 回归测试（内存库）。

锁定「删行重建 / Session 不失效 / 申请人同名提示」等旧策略不可接受。
"""
import inspect
import os
import unittest

from sqlalchemy import select

from tests.test_registration import _make_app

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestDisabledUserOverwriteIdentity(unittest.TestCase):
    """同名停用：保留 user_id，覆盖资料，禁止删行重建。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from datas.model.rbac_user import RbacUser
            from datas.model.resource_group import ResourceGroup
            from datas.model.user_group import UserGroup

            self.db.create_all()
            old_group = ResourceGroup(name='旧业务组')
            new_group = ResourceGroup(name='新业务组')
            self.db.session.add_all([old_group, new_group])
            self.db.session.flush()

            disabled = RbacUser(
                username='returning',
                role='viewer',
                is_active=0,
                email='old@corp.com',
                nickname='旧花名',
                job_title='qa',
                api_token=None,
                auth_version=1,
                create_time=100,
                last_login_at=200,
            )
            disabled.set_password('old-password')
            self.db.session.add(disabled)
            self.db.session.flush()
            self.old_user_id = disabled.id
            self.old_group_id = old_group.id
            self.new_group_id = new_group.id
            self.db.session.add(
                UserGroup(user_id=disabled.id, group_id=old_group.id)
            )

            req = RbacRegistrationRequest(
                email='returning@corp.com',
                username='returning',
                password_hash='placeholder',
                role='operator',
                group_ids=str(new_group.id),
                job_title='tech',
                nickname='新花名',
                reason='重新加入项目',
                status='pending',
                pending_username='returning',
                create_time=300,
                is_reactivation=1,
                target_user_id=disabled.id,
            )
            req.set_password('new-password')
            self.db.session.add(req)
            self.db.session.commit()
            self.request_id = req.id

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_approval_keeps_user_id_and_replaces_groups(self):
        with self.app.test_request_context():
            from flask import session

            from app.rbac.services import approve_registration

            session['user_id'] = 999
            session['username'] = 'admin'
            result = approve_registration(self.request_id)
            self.assertTrue(result['ok'], result)
            self.assertTrue(result.get('reactivated'))
            self.assertEqual(result['user_id'], self.old_user_id)

        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            from datas.model.user_group import UserGroup

            users = self.db.session.scalars(
                select(RbacUser).where(RbacUser.username == 'returning')
            ).all()
            self.assertEqual(len(users), 1)
            user = users[0]
            self.assertEqual(user.id, self.old_user_id)
            self.assertEqual(user.create_time, 100)
            self.assertEqual(user.last_login_at, 200)
            self.assertEqual(user.is_active, 1)
            self.assertEqual(user.role, 'operator')
            self.assertEqual(user.email, 'returning@corp.com')
            self.assertEqual(user.nickname, '新花名')
            self.assertEqual(user.job_title, 'tech')
            self.assertTrue(user.check_password('new-password'))
            self.assertIsNotNone(user.api_token)
            self.assertEqual(user.auth_version, 2)
            self.assertEqual(user.must_reset_password, 0)
            self.assertIn('同名覆盖启用', user.status_reason or '')
            group_ids = self.db.session.scalars(
                select(UserGroup.group_id).where(UserGroup.user_id == user.id)
            ).all()
            self.assertEqual(group_ids, [self.new_group_id])
            self.assertNotIn(self.old_group_id, group_ids)

    def test_admin_add_requires_confirmation_then_overwrites(self):
        with self.app.test_request_context():
            from app.rbac.services import create_user

            first = create_user(
                'returning',
                role='operator',
                email='admin-reset@corp.com',
                nickname='管理员覆盖',
                job_title='ops',
                group_ids=[self.new_group_id],
            )
            self.assertFalse(first['ok'])
            self.assertTrue(first.get('confirm_reactivation'))
            self.assertEqual(first.get('user_id'), self.old_user_id)

            confirmed = create_user(
                'returning',
                role='operator',
                email='admin-reset@corp.com',
                nickname='管理员覆盖',
                job_title='ops',
                group_ids=[self.new_group_id],
                confirm_reactivation=True,
            )
            self.assertTrue(confirmed['ok'], confirmed)
            self.assertTrue(confirmed.get('reactivated'))
            self.assertEqual(confirmed['user_id'], self.old_user_id)

        with self.app.app_context():
            from datas.model.rbac_user import RbacUser

            user = self.db.session.get(RbacUser, self.old_user_id)
            self.assertEqual(user.is_active, 1)
            self.assertEqual(user.nickname, '管理员覆盖')
            self.assertEqual(user.must_reset_password, 1)
            self.assertTrue(user.check_password('changeme'))
            self.assertEqual(user.status_reason, '管理员确认同名覆盖启用')
            from datas.model.user_group import UserGroup

            group_ids = self.db.session.scalars(
                select(UserGroup.group_id).where(UserGroup.user_id == user.id)
            ).all()
            self.assertEqual(group_ids, [self.new_group_id])
            self.assertNotIn(self.old_group_id, group_ids)

    def test_submit_registration_allows_disabled_username_without_hint(self):
        """申请人侧：同名停用可提交，响应不得含同名/恢复提示。"""
        with self.app.test_request_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest

            from app.rbac.services import submit_registration

            # 清掉 setUp 里已有的 pending，避免「已有待审批」干扰本断言
            pending = self.db.session.get(RbacRegistrationRequest, self.request_id)
            pending.status = 'rejected'
            pending.pending_username = None
            self.db.session.commit()

            result = submit_registration(
                email='returning@corp.com',
                password='ApplicantPass1',
                confirm_password='ApplicantPass1',
                role='viewer',
                group_ids=[self.new_group_id],
                job_title='tech',
                nickname='新申请人',
                reason='需要访问',
            )
            self.assertTrue(result['ok'], result)
            msg = result.get('msg') or ''
            for banned in ('曾被停用', '恢复', '同名停用', '覆盖', '将被替换'):
                self.assertNotIn(banned, msg)

            req = self.db.session.scalars(
                select(RbacRegistrationRequest).where(
                    RbacRegistrationRequest.username == 'returning',
                    RbacRegistrationRequest.status == 'pending',
                )
            ).first()
            self.assertIsNotNone(req)
            self.assertEqual(req.is_reactivation, 1)
            self.assertEqual(req.target_user_id, self.old_user_id)

    def test_direct_enable_still_forbidden(self):
        with self.app.test_request_context():
            from app.rbac.services import set_user_active, update_user

            r1 = set_user_active(self.old_user_id, 1, reason='想直接启用')
            self.assertFalse(r1['ok'])
            self.assertIn('不可', r1.get('msg', ''))

            r2 = update_user(self.old_user_id, is_active=1)
            self.assertFalse(r2['ok'])
            self.assertIn('不可', r2.get('msg', ''))

    def test_service_never_deletes_disabled_user_row(self):
        from app.rbac import services

        source = inspect.getsource(services)
        self.assertNotIn('db.session.delete(old_disabled)', source)
        # 生产路径不得删 RbacUser 实体行（组关系 delete 除外）
        self.assertNotRegex(
            source,
            r'db\.session\.delete\(\s*(?:old_disabled|existing|user)\s*\)',
        )


class TestDisabledSessionRevocation(unittest.TestCase):
    """停用后已登录 Web Session 必须失效（B1 锁定；B2 完善 fail-closed）。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.rbac_user import RbacUser
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401

            self.db.create_all()
            user = RbacUser(
                username='session_user',
                role='viewer',
                is_active=1,
                auth_version=0,
                email='session_user@corp.com',
                nickname='会话用户',
                job_title='tech',
                create_time=100,
            )
            user.set_password('password')
            self.db.session.add(user)
            self.db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_disable_revokes_existing_web_session(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['is_login'] = True
            sess['user_id'] = self.user_id
            sess['username'] = 'session_user'
            sess['role'] = 'viewer'
            sess['group_ids'] = []
            sess['auth_version'] = 0

        with self.app.test_request_context():
            from app.rbac.services import set_user_active

            result = set_user_active(
                self.user_id, 0, reason='离职', actor_user_id=999
            )
            self.assertTrue(result['ok'], result)

        response = client.get('/rbac/profile', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/rbac/login', response.headers.get('Location', ''))
        with client.session_transaction() as sess:
            self.assertNotIn('is_login', sess)

    def test_missing_auth_version_key_fails_closed(self):
        """§4.4：Session 缺 auth_version 键不得用 or 0 放行。"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['is_login'] = True
            sess['user_id'] = self.user_id
            sess['username'] = 'session_user'
            sess['role'] = 'viewer'
            sess['group_ids'] = []
            # 故意不写 auth_version

        response = client.get('/rbac/profile', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/rbac/login', response.headers.get('Location', ''))
        with client.session_transaction() as sess:
            self.assertNotIn('is_login', sess)

    def test_auth_version_mismatch_revokes_session(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['is_login'] = True
            sess['user_id'] = self.user_id
            sess['username'] = 'session_user'
            sess['role'] = 'viewer'
            sess['group_ids'] = []
            sess['auth_version'] = 0

        with self.app.app_context():
            from datas.model.rbac_user import RbacUser

            user = self.db.session.get(RbacUser, self.user_id)
            user.auth_version = 1
            self.db.session.commit()

        response = client.get('/rbac/profile', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/rbac/login', response.headers.get('Location', ''))


class TestAuthVersionOneTimeBump(unittest.TestCase):
    """OPT-P0-22 §4.4 一次性 bump 幂等。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.rbac_user import RbacUser
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401

            self.db.create_all()
            user = RbacUser(
                username='bump_user',
                role='viewer',
                is_active=1,
                auth_version=0,
                create_time=100,
            )
            user.set_password('password')
            self.db.session.add(user)
            self.db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_bump_once_increments_and_is_idempotent(self):
        from scripts.ensure_business_tables import _bump_auth_version_once

        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            from sqlalchemy import text

            _bump_auth_version_once()
            user = self.db.session.get(RbacUser, self.user_id)
            self.assertEqual(user.auth_version, 1)
            flag = self.db.session.execute(
                text(
                    "SELECT flag_name FROM cp_schema_flags "
                    "WHERE flag_name = 'opt_p0_22_auth_version_bump'"
                )
            ).first()
            self.assertIsNotNone(flag)

            _bump_auth_version_once()
            self.db.session.refresh(user)
            self.assertEqual(user.auth_version, 1)


class TestAtomicOverwriteServiceB3(unittest.TestCase):
    """B3：审计 detail、目标二次校验、失败回滚、凭据分支。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from datas.model.rbac_user import RbacUser
            from datas.model.resource_group import ResourceGroup
            from datas.model.user_group import UserGroup

            self.db.create_all()
            old_group = ResourceGroup(name='旧组-B3')
            new_group = ResourceGroup(name='新组-B3')
            self.db.session.add_all([old_group, new_group])
            self.db.session.flush()
            disabled = RbacUser(
                username='overwrite_b3',
                role='viewer',
                is_active=0,
                email='old-b3@corp.com',
                nickname='旧B3',
                job_title='qa',
                auth_version=3,
                create_time=10,
            )
            disabled.set_password('old-b3-pass')
            self.db.session.add(disabled)
            self.db.session.flush()
            self.user_id = disabled.id
            self.old_group_id = old_group.id
            self.new_group_id = new_group.id
            self.db.session.add(UserGroup(user_id=disabled.id, group_id=old_group.id))
            req = RbacRegistrationRequest(
                email='new-b3@corp.com',
                username='overwrite_b3',
                password_hash='placeholder',
                role='operator',
                group_ids=str(new_group.id),
                job_title='tech',
                nickname='新B3',
                reason='B3验收',
                status='pending',
                pending_username='overwrite_b3',
                create_time=20,
                is_reactivation=1,
                target_user_id=disabled.id,
            )
            req.set_password('ApplicantB3Pass')
            self.db.session.add(req)
            self.db.session.commit()
            self.request_id = req.id

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_audit_detail_has_before_after_without_secrets(self):
        with self.app.test_request_context():
            from flask import session

            from app.rbac.services import approve_registration

            session['user_id'] = 1
            session['username'] = 'admin'
            result = approve_registration(self.request_id)
            self.assertTrue(result['ok'], result)

        with self.app.app_context():
            import json

            from datas.model.rbac_audit_log import RbacAuditLog

            entry = self.db.session.scalars(
                select(RbacAuditLog)
                .where(RbacAuditLog.action == 'user:reactivate')
                .order_by(RbacAuditLog.id.desc())
            ).first()
            self.assertIsNotNone(entry)
            self.assertTrue(entry.detail)
            detail = json.loads(entry.detail)
            self.assertEqual(detail['source'], 'registration_approve')
            self.assertEqual(detail['user_id'], self.user_id)
            self.assertEqual(detail['request_id'], self.request_id)
            self.assertEqual(detail['before']['role'], 'viewer')
            self.assertEqual(detail['before']['group_ids'], [self.old_group_id])
            self.assertEqual(detail['after']['role'], 'operator')
            self.assertEqual(detail['after']['group_ids'], [self.new_group_id])
            blob = entry.detail.lower()
            for banned in ('password', 'api_token', 'changeme', 'applicantb3pass'):
                self.assertNotIn(banned, blob)

    def test_stale_target_already_active_rejects(self):
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser

            user = self.db.session.get(RbacUser, self.user_id)
            user.is_active = 1
            self.db.session.commit()

        with self.app.test_request_context():
            from flask import session

            from app.rbac.services import approve_registration

            session['user_id'] = 1
            session['username'] = 'admin'
            result = approve_registration(self.request_id)
            self.assertFalse(result['ok'])
            self.assertIn('已启用', result.get('msg', ''))

        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from datas.model.rbac_user import RbacUser
            from datas.model.user_group import UserGroup

            req = self.db.session.get(RbacRegistrationRequest, self.request_id)
            self.assertEqual(req.status, 'rejected')
            user = self.db.session.get(RbacUser, self.user_id)
            self.assertEqual(user.role, 'viewer')
            self.assertEqual(user.nickname, '旧B3')
            gids = self.db.session.scalars(
                select(UserGroup.group_id).where(UserGroup.user_id == self.user_id)
            ).all()
            self.assertEqual(gids, [self.old_group_id])

    def test_overwrite_failure_rolls_back_profile_and_groups(self):
        with self.app.test_request_context():
            from unittest.mock import patch

            from flask import session

            from app.rbac.services import approve_registration

            session['user_id'] = 1
            session['username'] = 'admin'
            with patch(
                'app.rbac.services._auto_issue_token',
                side_effect=RuntimeError('token boom'),
            ):
                result = approve_registration(self.request_id)
            self.assertFalse(result['ok'])

        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from datas.model.rbac_user import RbacUser
            from datas.model.user_group import UserGroup

            req = self.db.session.get(RbacRegistrationRequest, self.request_id)
            self.assertEqual(req.status, 'pending')
            user = self.db.session.get(RbacUser, self.user_id)
            self.assertEqual(user.is_active, 0)
            self.assertEqual(user.role, 'viewer')
            self.assertEqual(user.nickname, '旧B3')
            self.assertEqual(user.auth_version, 3)
            self.assertTrue(user.check_password('old-b3-pass'))
            gids = self.db.session.scalars(
                select(UserGroup.group_id).where(UserGroup.user_id == self.user_id)
            ).all()
            self.assertEqual(gids, [self.old_group_id])

    def test_admin_and_registration_share_overwrite_helper(self):
        from app.rbac import services

        source = inspect.getsource(services)
        self.assertIn('def _overwrite_disabled_user_inplace', source)
        self.assertGreaterEqual(source.count('_overwrite_disabled_user_inplace('), 3)


class TestApplicantSurfaceNoReactivationHints(unittest.TestCase):
    """申请人可见模板不得出现同名停用/恢复类文案（B1 静态门禁）。"""

    BANNED = (
        '曾被停用',
        '恢复申请',
        '本人回来',
        '旧账号将被替换',
        '同名停用',
        '覆盖启用',
    )

    def test_register_and_login_templates_have_no_same_name_hints(self):
        paths = [
            os.path.join(ROOT, 'app/templates/redesign/register.html'),
            os.path.join(ROOT, 'app/templates/redesign/login.html'),
        ]
        for path in paths:
            with open(path, 'r', encoding='utf-8') as fh:
                text = fh.read()
            for banned in self.BANNED:
                self.assertNotIn(
                    banned,
                    text,
                    msg='%s 不得含申请人同名提示「%s」' % (path, banned),
                )


class TestApproverAdminCopyB4(unittest.TestCase):
    """B4：审批人/管理员可见文案须对齐 §4.2（覆盖 + 日志继承）。"""

    def test_users_deactivate_copy(self):
        path = os.path.join(ROOT, 'app/templates/redesign/users.html')
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('停用后不可直接启用', text)
        self.assertIn('覆盖资料与权限并重新启用', text)
        self.assertNotIn('停用后不可恢复启用', text)
        self.assertIn('同名再占用须经审批人或管理员确认覆盖启用', text)

    def test_users_set_active_copy(self):
        path = os.path.join(ROOT, 'app/templates/redesign/users_set_active.html')
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('停用后不可直接启用', text)
        self.assertNotIn('停用后不可恢复启用', text)

    def test_user_form_status_copy(self):
        path = os.path.join(ROOT, 'app/templates/redesign/user_form.html')
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('停用（不可直接启用）', text)
        self.assertIn('已停用（不可直接启用）', text)
        self.assertNotIn('不可恢复', text)
        self.assertIn('cp:form-confirm-reactivation', text)
        self.assertIn('确认同名覆盖启用', text)
        self.assertIn('历史日志因同一 user_id 保留', text)

    def test_registration_review_copy(self):
        path = os.path.join(ROOT, 'app/templates/redesign/registration_review.html')
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('同名停用', text)
        self.assertNotIn('曾被停用', text)
        self.assertNotIn('将被替换', text)
        self.assertIn('历史日志将被继承', text)
        self.assertIn('申请人未必是原使用人', text)
        self.assertIn('is_reactivation', text)

    def test_ajax_form_hooks_confirm_reactivation(self):
        path = os.path.join(ROOT, 'app/static/js/common-redesign.js')
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('confirm_reactivation', text)
        self.assertIn('cp:form-confirm-reactivation', text)


if __name__ == '__main__':
    unittest.main()
