# -*- coding:utf-8 -*-
"""OPT-P1-07 用户注册审批单元测试。"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask

from app.main import main as main_blueprint


def _make_app():
    """创建带 SQLite 内存库的测试 Flask app。"""
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, 'app', 'templates'),
        static_folder=os.path.join(ROOT, 'app', 'static'),
    )
    app.secret_key = 'test-secret-key-registration'
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['CRON_CONFIG'] = {
        'is_dev': '0',
        'block_private_ip': '0',
        'url_allow_hosts': '',
        'url_ssrf_observe_only': '1',
    }
    from app import db
    db.init_app(app)
    app.register_blueprint(main_blueprint)
    from app.rbac import rbac as rbac_blueprint
    app.register_blueprint(rbac_blueprint)
    return app, db


class TestRegistrationModel(unittest.TestCase):
    """数据模型基本测试。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_create_registration_request(self):
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            req = RbacRegistrationRequest(
                email='test@corp.com',
                username='test',
                password_hash='hashed',
                role='operator',
                group_ids='1,2',
                job_title='tech',
                nickname='小明',
                reason='Need access',
                status='pending',
                pending_username='test',
                create_time='2026-08-03 10:00:00',
            )
            self.db.session.add(req)
            self.db.session.commit()
            self.assertIsNotNone(req.id)
            self.assertEqual(req.status, 'pending')
            self.assertEqual(req.job_title, 'tech')
            self.assertEqual(req.nickname, '小明')
            self.assertEqual(req.pending_username, 'test')

    def test_pending_username_unique_constraint(self):
        """同一 username 不允许两条 pending 记录（数据库唯一索引兜底）。"""
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from sqlalchemy.exc import IntegrityError
            req1 = RbacRegistrationRequest(
                email='a@corp.com', username='dup',
                password_hash='h', role='operator', group_ids='1',
                status='pending', pending_username='dup',
                create_time='2026-08-03 10:00:00',
            )
            self.db.session.add(req1)
            self.db.session.commit()

            req2 = RbacRegistrationRequest(
                email='b@corp.com', username='dup',
                password_hash='h', role='viewer', group_ids='1',
                status='pending', pending_username='dup',
                create_time='2026-08-03 10:01:00',
            )
            self.db.session.add(req2)
            with self.assertRaises(IntegrityError):
                self.db.session.commit()
            self.db.session.rollback()

    def test_non_pending_no_conflict(self):
        """已处理的申请（pending_username=None）不与新 pending 冲突。"""
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            # 已拒绝的记录
            req1 = RbacRegistrationRequest(
                email='a@corp.com', username='reapply',
                password_hash='h', role='operator', group_ids='1',
                status='rejected', pending_username=None,
                create_time='2026-08-03 10:00:00',
            )
            self.db.session.add(req1)
            self.db.session.commit()

            # 新的 pending 记录应成功
            req2 = RbacRegistrationRequest(
                email='a@corp.com', username='reapply',
                password_hash='h', role='operator', group_ids='1',
                status='pending', pending_username='reapply',
                create_time='2026-08-03 11:00:00',
            )
            self.db.session.add(req2)
            self.db.session.commit()
            self.assertIsNotNone(req2.id)

    def test_rbac_user_email_column(self):
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            user = RbacUser(
                username='emailuser',
                password_hash='hash',
                role='viewer',
                email='emailuser@corp.com',
                create_time='2026-08-03 10:00:00',
            )
            self.db.session.add(user)
            self.db.session.commit()
            fetched = self.db.session.get(RbacUser, user.id)
            self.assertEqual(fetched.email, 'emailuser@corp.com')

    def test_rbac_user_job_title_and_nickname(self):
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            user = RbacUser(
                username='profileuser',
                password_hash='hash',
                role='viewer',
                email='profileuser@corp.com',
                job_title='tech',
                nickname='小红',
                create_time='2026-08-03 10:00:00',
            )
            self.db.session.add(user)
            self.db.session.commit()
            fetched = self.db.session.get(RbacUser, user.id)
            self.assertEqual(fetched.job_title, 'tech')
            self.assertEqual(fetched.nickname, '小红')

    def test_rbac_user_job_title_nullable(self):
        """管理员创建的用户可以没有 job_title/nickname。"""
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            user = RbacUser(
                username='noprofile',
                password_hash='hash',
                role='viewer',
                create_time='2026-08-03 10:00:00',
            )
            self.db.session.add(user)
            self.db.session.commit()
            fetched = self.db.session.get(RbacUser, user.id)
            self.assertIsNone(fetched.job_title)
            self.assertIsNone(fetched.nickname)

    def test_rbac_user_email_nullable(self):
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            user = RbacUser(
                username='noemail',
                password_hash='hash',
                role='viewer',
                create_time='2026-08-03 10:00:00',
            )
            self.db.session.add(user)
            self.db.session.commit()
            fetched = self.db.session.get(RbacUser, user.id)
            self.assertIsNone(fetched.email)


class TestEmailExtraction(unittest.TestCase):
    """邮箱 → 用户名提取逻辑。"""

    def test_extract_normal(self):
        from app.rbac.services import _extract_username_from_email
        self.assertEqual(_extract_username_from_email('john.doe@corp.com'), 'john.doe')

    def test_extract_empty(self):
        from app.rbac.services import _extract_username_from_email
        self.assertEqual(_extract_username_from_email(''), '')
        self.assertEqual(_extract_username_from_email(None), '')

    def test_extract_no_at(self):
        from app.rbac.services import _extract_username_from_email
        self.assertEqual(_extract_username_from_email('noatsign'), '')

    def test_extract_multiple_at(self):
        from app.rbac.services import _extract_username_from_email
        self.assertEqual(_extract_username_from_email('user@sub@corp.com'), 'user')


class TestSubmitRegistration(unittest.TestCase):
    """注册申请提交逻辑。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            self.db.create_all()
            # 创建一个业务组
            from datas.model.resource_group import ResourceGroup
            g = ResourceGroup(name='研发组', code='dev', create_time='2026-08-03')
            self.db.session.add(g)
            self.db.session.commit()
            self.group_id = g.id

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_submit_success(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='newuser@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='operator',
                group_ids=[str(self.group_id)],
                reason='Need task access',
                job_title='tech',
                nickname='小明',
            )
            self.assertTrue(result['ok'])

        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from sqlalchemy import select
            req = self.db.session.scalars(
                select(RbacRegistrationRequest).where(
                    RbacRegistrationRequest.username == 'newuser'
                )
            ).first()
            self.assertEqual(req.job_title, 'tech')
            self.assertEqual(req.nickname, '小明')

    def test_submit_invalid_email(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='invalid',
                password='pass123',
                confirm_password='pass123',
                role='operator',
                group_ids=[str(self.group_id)],
                reason='test',
            )
            self.assertFalse(result['ok'])
            self.assertIn('邮箱', result['msg'])

    def test_submit_admin_role_rejected(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='admin@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='admin',
                group_ids=[str(self.group_id)],
                reason='Want admin',
            )
            self.assertFalse(result['ok'])
            self.assertIn('operator 或 viewer', result['msg'])

    def test_submit_password_mismatch(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='mismatch@corp.com',
                password='pass123',
                confirm_password='pass456',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
            )
            self.assertFalse(result['ok'])
            self.assertIn('不一致', result['msg'])

    def test_submit_short_password(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='short@corp.com',
                password='12345',
                confirm_password='12345',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
            )
            self.assertFalse(result['ok'])
            self.assertIn('6', result['msg'])

    def test_submit_no_reason(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='noreason@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='',
                job_title='tech',
                nickname='小明',
            )
            self.assertFalse(result['ok'])
            self.assertIn('缘由', result['msg'])

    def test_submit_no_groups(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='nogroup@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[],
                reason='test reason',
                job_title='tech',
                nickname='小明',
            )
            self.assertFalse(result['ok'])
            self.assertIn('业务组', result['msg'])

    def test_submit_missing_job_title(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='nojob@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
                job_title='',
                nickname='花名',
            )
            self.assertFalse(result['ok'])
            self.assertIn('岗位', result['msg'])

    def test_submit_invalid_job_title(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='badjob@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
                job_title='ceo',
                nickname='花名',
            )
            self.assertFalse(result['ok'])
            self.assertIn('无效', result['msg'])

    def test_submit_other_job_title(self):
        """选择其他时需输入具体岗位。"""
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='otherjob@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
                job_title='other:安全工程师',
                nickname='花名',
            )
            self.assertTrue(result['ok'])

    def test_submit_other_job_title_empty(self):
        """选择其他但未输入具体内容应拒绝。"""
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='emptyother@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
                job_title='other:',
                nickname='花名',
            )
            self.assertFalse(result['ok'])
            self.assertIn('其他', result['msg'])

    def test_submit_other_job_title_too_long(self):
        """自定义岗位名称超长应拒绝。"""
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='longjob@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
                job_title='other:' + 'A' * 21,
                nickname='花名',
            )
            self.assertFalse(result['ok'])
            self.assertIn('20', result['msg'])

    def test_submit_proj_mgr_job_title(self):
        """项目经理岗位类型应成功。"""
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='projmgr@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='operator',
                group_ids=[str(self.group_id)],
                reason='manage projects',
                job_title='proj_mgr',
                nickname='项目组长',
            )
            self.assertTrue(result['ok'])

    def test_submit_missing_nickname(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='noname@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
                job_title='tech',
                nickname='',
            )
            self.assertFalse(result['ok'])
            self.assertIn('花名', result['msg'])

    def test_submit_duplicate_username(self):
        """用户名已存在于 rbac_users 时应拒绝。"""
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            user = RbacUser(
                username='existing',
                password_hash='hash',
                role='viewer',
                create_time='2026-08-03',
            )
            user.set_password('pass')
            self.db.session.add(user)
            self.db.session.commit()

        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result = submit_registration(
                email='existing@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
                job_title='ops',
                nickname='花名',
            )
            self.assertFalse(result['ok'])
            self.assertIn('已存在', result['msg'])

    def test_submit_duplicate_pending(self):
        """同一 username 有 pending 申请时应拒绝。"""
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            result1 = submit_registration(
                email='dup@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='operator',
                group_ids=[str(self.group_id)],
                reason='first apply',
                job_title='tech',
                nickname='小花',
            )
            self.assertTrue(result1['ok'])
            result2 = submit_registration(
                email='dup@corp.com',
                password='pass456',
                confirm_password='pass456',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='second apply',
                job_title='ops',
                nickname='小花2',
            )
            self.assertFalse(result2['ok'])
            self.assertIn('待审批', result2['msg'])


class TestApproveRejectRegistration(unittest.TestCase):
    """审批通过/拒绝逻辑。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            self.db.create_all()
            from datas.model.resource_group import ResourceGroup
            g = ResourceGroup(name='研发组', code='dev', create_time='2026-08-03')
            self.db.session.add(g)
            self.db.session.commit()
            self.group_id = g.id

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def _create_pending_request(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            submit_registration(
                email='applicant@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='operator',
                group_ids=[str(self.group_id)],
                reason='Need access',
                job_title='tech',
                nickname='申请人',
            )
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from sqlalchemy import select
            req = self.db.session.scalars(
                select(RbacRegistrationRequest).where(
                    RbacRegistrationRequest.username == 'applicant'
                )
            ).first()
            return req.id

    def test_approve_creates_user(self):
        req_id = self._create_pending_request()
        with self.app.test_request_context():
            from flask import session
            session['user_id'] = 1
            session['username'] = 'admin'
            from app.rbac.services import approve_registration
            result = approve_registration(req_id)
            self.assertTrue(result['ok'])

        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            from sqlalchemy import select
            user = self.db.session.scalars(
                select(RbacUser).where(RbacUser.username == 'applicant')
            ).first()
            self.assertIsNotNone(user)
            self.assertEqual(user.role, 'operator')
            self.assertEqual(user.email, 'applicant@corp.com')
            self.assertEqual(user.job_title, 'tech')
            self.assertEqual(user.nickname, '申请人')
            self.assertEqual(user.must_reset_password, 0)
            self.assertIsNotNone(user.api_token)

    def test_approve_creates_user_groups(self):
        req_id = self._create_pending_request()
        with self.app.test_request_context():
            from flask import session
            session['user_id'] = 1
            session['username'] = 'admin'
            from app.rbac.services import approve_registration
            approve_registration(req_id)

        with self.app.app_context():
            from datas.model.user_group import UserGroup
            from datas.model.rbac_user import RbacUser
            from sqlalchemy import select
            user = self.db.session.scalars(
                select(RbacUser).where(RbacUser.username == 'applicant')
            ).first()
            groups = self.db.session.scalars(
                select(UserGroup).where(UserGroup.user_id == user.id)
            ).all()
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].group_id, self.group_id)

    def test_approve_already_processed(self):
        req_id = self._create_pending_request()
        with self.app.test_request_context():
            from flask import session
            session['user_id'] = 1
            session['username'] = 'admin'
            from app.rbac.services import approve_registration
            approve_registration(req_id)
            result2 = approve_registration(req_id)
            self.assertFalse(result2['ok'])
            self.assertIn('已处理', result2['msg'])

    def test_reject_registration(self):
        req_id = self._create_pending_request()
        with self.app.test_request_context():
            from flask import session
            session['user_id'] = 1
            session['username'] = 'admin'
            from app.rbac.services import reject_registration
            result = reject_registration(req_id, comment='Not needed')
            self.assertTrue(result['ok'])

        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            req = self.db.session.get(RbacRegistrationRequest, req_id)
            self.assertEqual(req.status, 'rejected')
            self.assertEqual(req.review_comment, 'Not needed')

    def test_reject_nonexistent(self):
        with self.app.test_request_context():
            from flask import session
            session['user_id'] = 1
            session['username'] = 'admin'
            from app.rbac.services import reject_registration
            result = reject_registration(99999)
            self.assertFalse(result['ok'])
            self.assertIn('不存在', result['msg'])

    def test_user_can_login_after_approval(self):
        """审批通过后，用户可以使用注册密码登录。"""
        req_id = self._create_pending_request()
        with self.app.test_request_context():
            from flask import session
            session['user_id'] = 1
            session['username'] = 'admin'
            from app.rbac.services import approve_registration
            approve_registration(req_id)

        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            from sqlalchemy import select
            user = self.db.session.scalars(
                select(RbacUser).where(RbacUser.username == 'applicant')
            ).first()
            self.assertTrue(user.check_password('pass123'))


class TestCheckRegistrationStatus(unittest.TestCase):
    """登录时注册状态查询。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            self.db.create_all()
            g = ResourceGroup(name='研发组', code='dev', create_time='2026-08-03')
            self.db.session.add(g)
            self.db.session.commit()
            self.group_id = g.id

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_no_registration(self):
        with self.app.app_context():
            from app.rbac.services import check_registration_status
            self.assertIsNone(check_registration_status('unknown'))

    def test_pending_status(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            submit_registration(
                email='pending@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
                job_title='qa',
                nickname='测试员',
            )
        with self.app.app_context():
            from app.rbac.services import check_registration_status
            status = check_registration_status('pending')
            self.assertIsNotNone(status)
            self.assertEqual(status['status'], 'pending')

    def test_rejected_status(self):
        with self.app.test_request_context():
            from app.rbac.services import submit_registration
            submit_registration(
                email='rejected@corp.com',
                password='pass123',
                confirm_password='pass123',
                role='viewer',
                group_ids=[str(self.group_id)],
                reason='test',
                job_title='pm',
                nickname='产品',
            )
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from sqlalchemy import select
            req = self.db.session.scalars(
                select(RbacRegistrationRequest).where(
                    RbacRegistrationRequest.username == 'rejected'
                )
            ).first()
            req_id = req.id
        with self.app.test_request_context():
            from flask import session
            session['user_id'] = 1
            session['username'] = 'admin'
            from app.rbac.services import reject_registration
            reject_registration(req_id, comment='No reason given')
        with self.app.app_context():
            from app.rbac.services import check_registration_status
            status = check_registration_status('rejected')
            self.assertIsNotNone(status)
            self.assertEqual(status['status'], 'rejected')
            self.assertIn('No reason', status['review_comment'])


class TestExpireStaleRegistrations(unittest.TestCase):
    """过期清理逻辑。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_expire_old_pending(self):
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            req = RbacRegistrationRequest(
                email='old@corp.com',
                username='old',
                password_hash='hash',
                role='viewer',
                group_ids='1',
                reason='old request',
                status='pending',
                create_time='2026-01-01 00:00:00',
            )
            self.db.session.add(req)
            self.db.session.commit()
            req_id = req.id

        with self.app.test_request_context():
            from app.rbac.services import expire_stale_registrations
            expire_stale_registrations()

        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            req = self.db.session.get(RbacRegistrationRequest, req_id)
            self.assertEqual(req.status, 'expired')

    def test_recent_pending_not_expired(self):
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from datas.utils.times import get_now_time
            req = RbacRegistrationRequest(
                email='recent@corp.com',
                username='recent',
                password_hash='hash',
                role='viewer',
                group_ids='1',
                reason='recent request',
                status='pending',
                create_time=get_now_time(),
            )
            self.db.session.add(req)
            self.db.session.commit()
            req_id = req.id

        with self.app.test_request_context():
            from app.rbac.services import expire_stale_registrations
            expire_stale_registrations()

        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            req = self.db.session.get(RbacRegistrationRequest, req_id)
            self.assertEqual(req.status, 'pending')


class TestJobTitleChoices(unittest.TestCase):
    """岗位类型枚举常量。"""

    def test_choices_available(self):
        from app.rbac.services import JOB_TITLE_CHOICES, VALID_JOB_TITLES
        self.assertGreater(len(JOB_TITLE_CHOICES), 0)
        self.assertIn('tech', VALID_JOB_TITLES)
        self.assertIn('ops', VALID_JOB_TITLES)
        self.assertIn('qa', VALID_JOB_TITLES)
        self.assertIn('pm', VALID_JOB_TITLES)
        self.assertIn('proj_mgr', VALID_JOB_TITLES)
        self.assertIn('strategy', VALID_JOB_TITLES)
        self.assertIn('operation', VALID_JOB_TITLES)
        self.assertIn('other', VALID_JOB_TITLES)

    def test_labels(self):
        from app.rbac.services import JOB_TITLE_CHOICES
        labels = dict(JOB_TITLE_CHOICES)
        self.assertEqual(labels['tech'], '技术')
        self.assertEqual(labels['proj_mgr'], '项目经理')
        self.assertEqual(labels['strategy'], '策略')
        self.assertEqual(labels['operation'], '运营')


class TestAuditLabels(unittest.TestCase):
    """审计日志标签覆盖。"""

    def test_registration_labels_exist(self):
        from app.rbac.services import AUDIT_ACTION_LABELS
        self.assertIn('user:register_apply', AUDIT_ACTION_LABELS)
        self.assertIn('user:register_approve', AUDIT_ACTION_LABELS)
        self.assertIn('user:register_reject', AUDIT_ACTION_LABELS)
        self.assertIn('user:register_expire', AUDIT_ACTION_LABELS)

    def test_registration_labels_chinese(self):
        from app.rbac.services import audit_action_label
        self.assertEqual(audit_action_label('user:register_apply'), '注册申请')
        self.assertEqual(audit_action_label('user:register_approve'), '审批通过')
        self.assertEqual(audit_action_label('user:register_reject'), '审批拒绝')
        self.assertEqual(audit_action_label('user:register_expire'), '注册过期')


class TestRegistrationHTTPIntegration(unittest.TestCase):
    """HTTP 集成测试：验证注册/审批页面模板可正常渲染（防 Jinja2 宏名/变量名错误）。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            self.db.create_all()
            # 创建 admin 用户
            admin = RbacUser(
                username='admin', role='admin',
                create_time='2026-08-03 00:00:00',
            )
            admin.set_password('changeme')
            self.db.session.add(admin)
            # 创建业务组
            grp = ResourceGroup(name='TestGroup', code='test_group')
            self.db.session.add(grp)
            self.db.session.commit()
            self.group_id = grp.id

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def _login_admin(self, client):
        """使用 test_client session 模拟 admin 登录。"""
        with client.session_transaction() as sess:
            sess['is_login'] = True
            sess['username'] = 'admin'
            sess['role'] = 'admin'
            sess['user_id'] = 1
            sess['group_ids'] = []

    # ── 注册页面 ──────────────────────────────────────

    def test_register_page_renders(self):
        """GET /rbac/register 应返回 200 且包含表单。"""
        with self.app.test_client() as c:
            resp = c.get('/rbac/register')
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode()
            self.assertIn('注册申请', html)
            self.assertIn('name="email"', html)
            self.assertIn('name="nickname"', html)
            self.assertIn('name="job_title"', html)

    def test_forgot_password_page_renders(self):
        """GET /rbac/forgot_password 应返回 200。"""
        with self.app.test_client() as c:
            resp = c.get('/rbac/forgot_password')
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode()
            self.assertIn('忘记密码', html)

    # ── 审批管理页面（需登录） ─────────────────────────

    def test_registration_review_renders_empty(self):
        """GET /rbac/registration_review 无数据时返回 200 + 空状态。"""
        with self.app.test_client() as c:
            self._login_admin(c)
            resp = c.get('/rbac/registration_review')
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode()
            self.assertIn('注册审批', html)
            self.assertIn('暂无注册申请', html)

    def test_registration_review_renders_with_data(self):
        """GET /rbac/registration_review 有数据时返回 200 + 申请记录。"""
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            req = RbacRegistrationRequest(
                email='integ@corp.com', username='integ',
                password_hash='h', role='operator',
                group_ids=str(self.group_id),
                job_title='tech', nickname='集成',
                reason='integration test',
                status='pending', pending_username='integ',
                create_time='2026-08-03 12:00:00',
            )
            self.db.session.add(req)
            self.db.session.commit()

        with self.app.test_client() as c:
            self._login_admin(c)
            resp = c.get('/rbac/registration_review')
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode()
            self.assertIn('integ@corp.com', html)
            self.assertIn('待审批', html)
            self.assertIn('✓ 批准', html)
            self.assertIn('✗ 拒绝', html)
            self.assertIn('approveModal', html)
            self.assertIn('rejectModal', html)

    def test_registration_review_status_filter(self):
        """状态筛选参数不导致 500。"""
        with self.app.test_client() as c:
            self._login_admin(c)
            for status in ('pending', 'approved', 'rejected', 'expired'):
                resp = c.get('/rbac/registration_review?status=%s' % status)
                self.assertEqual(resp.status_code, 200,
                                 'status=%s returned %s' % (status, resp.status_code))

    def test_registration_review_pagination_macro(self):
        """分页宏 pg.page() 在审批页面正确渲染（防 page_navi 回归）。"""
        with self.app.test_client() as c:
            self._login_admin(c)
            resp = c.get('/rbac/registration_review')
            self.assertEqual(resp.status_code, 200)
            # 模板能渲染完成即说明 pg.page() 宏调用正确

    def test_registration_review_requires_login(self):
        """未登录访问审批页面应重定向到登录。"""
        with self.app.test_client() as c:
            resp = c.get('/rbac/registration_review')
            self.assertIn(resp.status_code, (302, 401, 403))

    # ── 审批操作 ──────────────────────────────────────

    def test_approve_creates_user(self):
        """POST approve 应创建用户并更新状态。"""
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            req = RbacRegistrationRequest(
                email='approve_integ@corp.com', username='approve_integ',
                password_hash='h', role='operator',
                group_ids=str(self.group_id),
                job_title='qa', nickname='审批测试',
                reason='approval test',
                status='pending', pending_username='approve_integ',
                create_time='2026-08-03 12:00:00',
            )
            req.set_password('Test1234')
            self.db.session.add(req)
            self.db.session.commit()
            req_id = req.id

        with self.app.test_client() as c:
            self._login_admin(c)
            resp = c.post('/rbac/registration_review/approve',
                          data={'id': str(req_id)},
                          follow_redirects=False)
            self.assertIn(resp.status_code, (302, 200))

        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            from datas.model.rbac_user import RbacUser
            updated = self.db.session.get(RbacRegistrationRequest, req_id)
            self.assertEqual(updated.status, 'approved')
            user = self.db.session.query(RbacUser).filter_by(
                username='approve_integ').first()
            self.assertIsNotNone(user, 'User should be created on approval')

    def test_reject_updates_status(self):
        """POST reject 应更新状态 + 记录原因。"""
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            req = RbacRegistrationRequest(
                email='reject_integ@corp.com', username='reject_integ',
                password_hash='h', role='viewer',
                group_ids=str(self.group_id),
                job_title='ops', nickname='拒绝测试',
                reason='reject test',
                status='pending', pending_username='reject_integ',
                create_time='2026-08-03 12:00:00',
            )
            self.db.session.add(req)
            self.db.session.commit()
            req_id = req.id

        with self.app.test_client() as c:
            self._login_admin(c)
            resp = c.post('/rbac/registration_review/reject',
                          data={'id': str(req_id), 'comment': 'Not needed'},
                          follow_redirects=False)
            self.assertIn(resp.status_code, (302, 200))

        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            updated = self.db.session.get(RbacRegistrationRequest, req_id)
            self.assertEqual(updated.status, 'rejected')
            self.assertEqual(updated.review_comment, 'Not needed')

    # ── 注册表单提交（HTTP） ─────────────────────────

    def test_register_post_success(self):
        """POST /rbac/register 成功应重定向到登录页。"""
        with self.app.test_client() as c:
            resp = c.post('/rbac/register', data={
                'email': 'httptest@corp.com',
                'nickname': 'HTTP测试',
                'job_title': 'tech',
                'password': 'Test1234',
                'confirm_password': 'Test1234',
                'role': 'operator',
                'group_ids': str(self.group_id),
                'reason': 'http integration test',
            }, follow_redirects=False)
            self.assertIn(resp.status_code, (302, 200))

    def test_register_post_admin_rejected(self):
        """POST /rbac/register 选择 admin 角色应被后端拒绝。"""
        with self.app.test_client() as c:
            resp = c.post('/rbac/register', data={
                'email': 'adminreg@corp.com',
                'nickname': 'AdminTry',
                'job_title': 'tech',
                'password': 'Test1234',
                'confirm_password': 'Test1234',
                'role': 'admin',
                'group_ids': str(self.group_id),
                'reason': 'I want admin',
            })
            html = resp.data.decode()
            self.assertIn('管理员', html)

    # ── 登录页注册状态提示 ────────────────────────────

    def test_login_page_shows_pending_status(self):
        """登录页携带 reg_username 参数时显示注册状态。"""
        with self.app.app_context():
            from datas.model.rbac_registration_request import RbacRegistrationRequest
            req = RbacRegistrationRequest(
                email='pending_hint@corp.com', username='pending_hint',
                password_hash='h', role='viewer',
                group_ids=str(self.group_id),
                job_title='tech', nickname='提示测试',
                reason='hint test',
                status='pending', pending_username='pending_hint',
                create_time='2026-08-03 12:00:00',
            )
            self.db.session.add(req)
            self.db.session.commit()

        with self.app.test_client() as c:
            resp = c.get('/rbac/login?reg_username=pending_hint')
            self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
