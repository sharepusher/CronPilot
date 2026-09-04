# -*- coding:utf-8 -*-
"""OPT-P2-12 Resource Scope 单测。"""
import os
import unittest
from types import SimpleNamespace

from flask import Flask

from app.rbac.authorize import AuthorizationError, authorize
from app.rbac.policy import has_permission, role_bypasses_scope, user_bypasses_scope
from app.rbac.scope import (
    SCOPE_GLOBAL,
    SCOPE_GROUP,
    build_scope_filter_clause,
    has_scope,
    normalize_scope_fields,
    user_can_assign_group,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestScopePure(unittest.TestCase):
    def test_admin_bypasses_scope(self):
        self.assertTrue(role_bypasses_scope('admin'))
        self.assertFalse(role_bypasses_scope('operator'))
        self.assertFalse(role_bypasses_scope('viewer'))

    def test_normalize_global_clears_group(self):
        err, st, gid = normalize_scope_fields('GLOBAL', group_id=99)
        self.assertIsNone(err)
        self.assertEqual(st, SCOPE_GLOBAL)
        self.assertIsNone(gid)

    def test_normalize_group_requires_id(self):
        err, st, gid = normalize_scope_fields('GROUP', group_id=None)
        self.assertIsNotNone(err)
        err, st, gid = normalize_scope_fields('GROUP', group_id=3)
        self.assertIsNone(err)
        self.assertEqual(st, SCOPE_GROUP)
        self.assertEqual(gid, 3)

    def test_has_scope_global_no_db(self):
        """GLOBAL 资源对任何角色可见（不需要 task_groups 查询）。"""
        glob = SimpleNamespace(scope_type='GLOBAL', id=999)
        self.assertTrue(has_scope('viewer', [1], glob))
        self.assertTrue(has_scope('operator', [], glob))

    def test_has_scope_admin_bypass(self):
        """seed admin 和全局 admin 绕过 scope。"""
        grp = SimpleNamespace(scope_type='GROUP', id=999)
        self.assertTrue(has_scope('admin', [], grp, username='admin'))
        self.assertTrue(has_scope('admin', [], grp, username='mgr'))

    def test_user_can_assign_group(self):
        self.assertTrue(user_can_assign_group('admin', [], 9, username='admin'))
        self.assertTrue(user_can_assign_group('admin', [], 9, username='mgr'))
        self.assertFalse(user_can_assign_group('admin', [1], 9, username='mgr'))
        self.assertTrue(user_can_assign_group('admin', [1, 9], 9, username='mgr'))
        self.assertTrue(user_can_assign_group('operator', [1, 2], 1))
        self.assertFalse(user_can_assign_group('operator', [1], 2))

    def test_build_scope_filter_admin_none(self):
        self.assertIsNone(build_scope_filter_clause('admin', [], username='admin'))
        self.assertIsNone(build_scope_filter_clause('admin', [], username='mgr'))
        self.assertIsNotNone(build_scope_filter_clause('admin', [1], username='mgr'))

    def test_user_bypasses_scope(self):
        self.assertTrue(user_bypasses_scope('admin', username='admin', group_ids=[]))
        self.assertTrue(user_bypasses_scope('admin', username='admin', group_ids=[1, 2]))
        self.assertTrue(user_bypasses_scope('admin', username='mgr', group_ids=[]))
        self.assertTrue(user_bypasses_scope('admin', username='mgr', group_ids=None))
        self.assertFalse(user_bypasses_scope('admin', username='mgr', group_ids=[1]))
        self.assertFalse(user_bypasses_scope('operator', username='op', group_ids=[]))
        self.assertFalse(user_bypasses_scope('viewer', username='vw', group_ids=[]))

    def test_authorize_permission_denied(self):
        """viewer 无 cron:write 权限。"""
        other = SimpleNamespace(scope_type='GROUP', id=9)
        with self.assertRaises(AuthorizationError) as cm:
            authorize('viewer', 'cron:write', other, group_ids=[1])
        self.assertEqual(cm.exception.kind, 'permission')

    def test_authorize_admin_bypass(self):
        """全局 admin 绕过 scope 检查。"""
        other = SimpleNamespace(scope_type='GROUP', id=9)
        authorize('admin', 'cron:write', other, group_ids=[], username='mgr_admin')

    def test_authorize_global_resource(self):
        """GLOBAL 资源对 operator 可见。"""
        glob = SimpleNamespace(scope_type='GLOBAL', id=1)
        authorize('operator', 'cron:write', glob, group_ids=[])


class TestGroupCodeAndMembership(unittest.TestCase):
    def test_non_admin_requires_groups(self):
        from app.rbac.services import validate_groups_for_role

        self.assertEqual(validate_groups_for_role('admin', [], username='admin'), '')
        self.assertIn('必须', validate_groups_for_role('admin', [], username='mgr_admin'))
        self.assertEqual(validate_groups_for_role('admin', ['__ALL__'], username='mgr_admin'), '')
        self.assertIn('必须', validate_groups_for_role('viewer', []))
        self.assertIn('必须', validate_groups_for_role('operator', []))
        self.assertEqual(validate_groups_for_role('operator', [1]), '')

    def test_validate_all_marker_mutual_exclusion(self):
        from app.rbac.services import validate_groups_for_role

        self.assertIn('不能同时', validate_groups_for_role('admin', ['__ALL__', '1'], username='mgr'))
        self.assertEqual(validate_groups_for_role('admin', ['__ALL__'], username='mgr'), '')
        self.assertEqual(validate_groups_for_role('admin', [1, 2], username='mgr'), '')


class TestScopeIntegration(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['CRON_CONFIG'] = {
            'is_dev': '0',
            'block_private_ip': '0',
            'url_allow_hosts': '',
            'url_ssrf_observe_only': '1',
        }
        from app import db
        db.init_app(app)
        from app.main import main as main_blueprint
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(main_blueprint)
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.db = db
        self.client = app.test_client()
        with app.app_context():
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            db.create_all()
            self._seed()

    def _seed(self):
        from datas.model.cron_infos import CronInfos
        from datas.model.rbac_user import RbacUser
        from datas.model.resource_group import ResourceGroup
        from datas.model.user_group import UserGroup
        from datas.model.task_group import TaskGroup
        from datas.utils.times import utc_now_hms

        g1 = ResourceGroup(name='组A', description='', create_time=utc_now_hms())
        g2 = ResourceGroup(name='组B', description='', create_time=utc_now_hms())
        self.db.session.add_all([g1, g2])
        self.db.session.flush()
        self.g1_id = g1.id
        self.g2_id = g2.id

        op = RbacUser(username='op_a', role='operator', is_active=1, create_time=utc_now_hms())
        op.set_password('pass')
        vw = RbacUser(username='vw_a', role='viewer', is_active=1, create_time=utc_now_hms())
        vw.set_password('pass')
        adm = RbacUser(username='adm', role='admin', is_active=1, create_time=utc_now_hms())
        adm.set_password('pass')
        self.db.session.add_all([op, vw, adm])
        self.db.session.flush()
        self.db.session.add(UserGroup(user_id=op.id, group_id=g1.id))
        self.db.session.add(UserGroup(user_id=vw.id, group_id=g1.id))

        now = utc_now_hms()
        c_global = CronInfos(
            task_name='global_task',
            task_keyword='kw',
            req_url='https://example.com/g',
            status=1,
            created_at=now,
            updated_at=now,
            scope_type='GLOBAL',
        )
        c_a = CronInfos(
            task_name='group_a_task',
            task_keyword='kw',
            req_url='https://example.com/a',
            status=1,
            created_at=now,
            updated_at=now,
            scope_type='GROUP',
        )
        c_b = CronInfos(
            task_name='group_b_task',
            task_keyword='kw',
            req_url='https://example.com/b',
            status=1,
            created_at=now,
            updated_at=now,
            scope_type='GROUP',
        )
        self.db.session.add_all([c_global, c_a, c_b])
        self.db.session.flush()
        # OPT-P1-11：组关系通过 task_groups 表维护
        self.db.session.add(TaskGroup(task_id=c_a.id, group_id=g1.id))
        self.db.session.add(TaskGroup(task_id=c_b.id, group_id=g2.id))
        self.db.session.commit()
        self.global_id = c_global.id
        self.a_id = c_a.id
        self.b_id = c_b.id

    def _login(self, username):
        resp = self.client.post(
            '/rbac/login',
            data={'username': username, 'password': 'pass', 'next': '/cron_list'},
        )
        self.assertEqual(resp.status_code, 302)

    def test_list_hides_other_group(self):
        self._login('op_a')
        resp = self.client.get('/cron_list')
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('global_task', body)
        self.assertIn('group_a_task', body)
        self.assertNotIn('group_b_task', body)

    def test_edit_other_group_forbidden(self):
        self._login('op_a')
        resp = self.client.get('/cron_edit?id=%s' % self.b_id)
        self.assertEqual(resp.status_code, 403)

    def test_viewer_sees_global_and_own_group(self):
        self._login('vw_a')
        resp = self.client.get('/cron_list')
        body = resp.get_data(as_text=True)
        self.assertIn('global_task', body)
        self.assertIn('group_a_task', body)
        self.assertNotIn('group_b_task', body)

    def test_admin_sees_all(self):
        self._login('adm')
        resp = self.client.get('/cron_list')
        body = resp.get_data(as_text=True)
        self.assertIn('group_b_task', body)

    def test_login_sets_group_ids(self):
        self._login('op_a')
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('group_ids'), [self.g1_id])

    def test_default_scope_columns(self):
        from datas.model.cron_infos import CronInfos
        from app.rbac.scope import get_task_group_ids

        with self.app.app_context():
            cif = self.db.session.get(CronInfos, self.global_id)
            self.assertEqual(cif.scope_type, 'GLOBAL')
            self.assertEqual(get_task_group_ids(cif.id), [])

    def test_has_scope_group_via_task_groups(self):
        """OPT-P1-11：has_scope 对 GROUP 任务通过 task_groups 表判断。"""
        from datas.model.cron_infos import CronInfos
        from app.rbac.scope import has_scope

        with self.app.app_context():
            cif_a = self.db.session.get(CronInfos, self.a_id)
            cif_b = self.db.session.get(CronInfos, self.b_id)
            # op_a 属于 g1，应可见 group_a_task（在 g1 中）
            self.assertTrue(has_scope('operator', [self.g1_id], cif_a))
            # op_a 属于 g1，不可见 group_b_task（在 g2 中）
            self.assertFalse(has_scope('operator', [self.g1_id], cif_b))
            # 双组用户可见两个任务
            self.assertTrue(has_scope('operator', [self.g1_id, self.g2_id], cif_b))
            # 无组用户只能看 GLOBAL
            self.assertFalse(has_scope('operator', [], cif_a))
            # 管理员 admin 全局 bypass
            self.assertTrue(has_scope('admin', [], cif_b, username='admin'))
            # 管理员 mgr 有组限制
            self.assertFalse(has_scope('admin', [self.g1_id], cif_b, username='mgr'))
            self.assertTrue(has_scope('admin', [self.g2_id], cif_b, username='mgr'))

    def test_authorize_operator_scope_denied(self):
        """OPT-P1-11：operator 对不在其组内的 GROUP 任务 scope 拒绝。"""
        from datas.model.cron_infos import CronInfos
        from app.rbac.authorize import authorize, AuthorizationError

        with self.app.app_context():
            cif_b = self.db.session.get(CronInfos, self.b_id)
            with self.assertRaises(AuthorizationError) as cm:
                authorize('operator', 'cron:write', cif_b, group_ids=[self.g1_id])
            self.assertEqual(cm.exception.kind, 'scope')

    def test_multi_group_operator_sees_both(self):
        """OPT-P1-16 回归：双组 operator 可见两个组的任务 + GLOBAL。"""
        from datas.model.rbac_user import RbacUser
        from datas.model.user_group import UserGroup
        from datas.utils.times import utc_now_hms

        with self.app.app_context():
            multi_op = RbacUser(username='op_multi', role='operator',
                                is_active=1, create_time=utc_now_hms())
            multi_op.set_password('pass')
            self.db.session.add(multi_op)
            self.db.session.flush()
            self.db.session.add(UserGroup(user_id=multi_op.id, group_id=self.g1_id))
            self.db.session.add(UserGroup(user_id=multi_op.id, group_id=self.g2_id))
            self.db.session.commit()

        self._login('op_multi')
        resp = self.client.get('/cron_list')
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('global_task', body)
        self.assertIn('group_a_task', body)
        self.assertIn('group_b_task', body)

    def test_biz_admin_with_group_is_scoped(self):
        """OPT-P1-16 回归：Biz Admin 有 group_ids 时受 scope 限制（仅看自己组 + GLOBAL）。"""
        from datas.model.rbac_user import RbacUser
        from datas.model.user_group import UserGroup
        from datas.utils.times import utc_now_hms

        with self.app.app_context():
            biz_adm = RbacUser(username='biz_adm_g1', role='admin',
                               is_active=1, create_time=utc_now_hms())
            biz_adm.set_password('pass')
            self.db.session.add(biz_adm)
            self.db.session.flush()
            self.db.session.add(UserGroup(user_id=biz_adm.id, group_id=self.g1_id))
            self.db.session.commit()

        self._login('biz_adm_g1')
        resp = self.client.get('/cron_list')
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('global_task', body, "Biz admin should see GLOBAL tasks")
        self.assertIn('group_a_task', body, "Biz admin should see own group tasks")
        self.assertNotIn('group_b_task', body,
                         "Biz admin with group_ids should NOT see other group tasks")


class TestAuditLogActorGroups(unittest.TestCase):
    """OPT-P2-13 审计日志 actor_group_ids 写入 + 查询过滤验证。"""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        self.app.config['TESTING'] = True
        self.app.secret_key = 'test-audit-scope'

        from app import db
        self.db = db
        db.init_app(self.app)

        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog
            db.create_all()
            self._seed_audit_data()

    def _seed_audit_data(self):
        """写入测试审计数据，覆盖各种 actor_group_ids 场景。"""
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.utils.times import str_to_hms

        entries = [
            RbacAuditLog(id=1, username='admin', action='user:login',
                         resource='admin', actor_group_ids='',
                         create_time=str_to_hms('2026-07-31 10:00:00')),
            RbacAuditLog(id=2, username='mgr_a', action='user:login',
                         resource='mgr_a', actor_group_ids=',1,2,',
                         create_time=str_to_hms('2026-07-31 10:01:00')),
            RbacAuditLog(id=3, username='mgr_b', action='user:password_reset',
                         resource='user_x', actor_group_ids=',3,4,',
                         create_time=str_to_hms('2026-07-31 10:02:00')),
            RbacAuditLog(id=4, username='user_x', action='user:login',
                         resource='user_x', actor_group_ids=',1,3,',
                         create_time=str_to_hms('2026-07-31 10:03:00')),
            RbacAuditLog(id=5, username='user_y', action='permission:deny',
                         resource='cron:write', actor_group_ids=',2,',
                         status='deny', create_time=str_to_hms('2026-07-31 10:04:00')),
            RbacAuditLog(id=6, username='old_user', action='user:login',
                         resource='old_user', actor_group_ids='',
                         create_time=str_to_hms('2026-07-01 10:00:00')),
        ]
        for e in entries:
            self.db.session.add(e)
        self.db.session.commit()

    def test_write_audit_log_records_actor_groups(self):
        """write_audit_log 写入 actor_group_ids 逗号包围格式。"""
        from datas.model.rbac_audit_log import RbacAuditLog
        from app.rbac.services import write_audit_log

        with self.app.test_request_context('/'):
            from flask import session
            session['user_id'] = 42
            session['username'] = 'test_mgr'
            session['group_ids'] = [1, 3]

            write_audit_log(action='user:login', resource='test_mgr')

            entry = self.db.session.query(RbacAuditLog).filter_by(
                username='test_mgr'
            ).first()
            self.assertIsNotNone(entry)
            self.assertEqual(entry.actor_group_ids, ',1,3,')
            self.assertEqual(entry.username, 'test_mgr')

    def test_write_audit_log_empty_groups(self):
        """种子 admin 或未登录时 actor_group_ids 为空。"""
        from datas.model.rbac_audit_log import RbacAuditLog
        from app.rbac.services import write_audit_log

        with self.app.test_request_context('/'):
            from flask import session
            session['user_id'] = 1
            session['username'] = 'admin_seed_test'
            session['group_ids'] = []

            write_audit_log(action='user:login', resource='admin_seed_test')

            entry = self.db.session.query(RbacAuditLog).filter_by(
                username='admin_seed_test'
            ).first()
            self.assertIsNotNone(entry)
            self.assertEqual(entry.actor_group_ids, '')

    def test_actor_group_ids_csv_format(self):
        """验证逗号包围格式。"""
        from app.rbac.services import _actor_group_ids_csv

        with self.app.test_request_context('/'):
            from flask import session

            session['group_ids'] = [5, 10, 20]
            self.assertEqual(_actor_group_ids_csv(), ',5,10,20,')

            session['group_ids'] = [7]
            self.assertEqual(_actor_group_ids_csv(), ',7,')

            session['group_ids'] = []
            self.assertEqual(_actor_group_ids_csv(), '')

            session.pop('group_ids', None)
            self.assertEqual(_actor_group_ids_csv(), '')

    def test_paginate_all_returns_everything(self):
        """bypass 用户（种子/全局 admin）调 paginate_all 看到全部。"""
        from app.repositories.rbac_audit_log_repository import RbacAuditLogRepository
        from app.services.pagination import PageQuery

        with self.app.app_context():
            repo = RbacAuditLogRepository(self.db.session)
            pq = PageQuery(page=1, per_page=50)
            page = repo.paginate_all(pq)
            self.assertEqual(len(page.items), 6)

    def test_paginate_by_scope_filters_by_group(self):
        """按组管理员仅看到 actor_group_ids 有交集的记录。"""
        from app.repositories.rbac_audit_log_repository import RbacAuditLogRepository
        from app.services.pagination import PageQuery

        with self.app.app_context():
            repo = RbacAuditLogRepository(self.db.session)
            pq = PageQuery(page=1, per_page=50)

            page = repo.paginate_by_scope(pq, [1, 2])
            visible_ids = {item.id for item in page.items}
            self.assertIn(2, visible_ids)
            self.assertIn(4, visible_ids)
            self.assertIn(5, visible_ids)
            self.assertNotIn(1, visible_ids)
            self.assertNotIn(3, visible_ids)
            self.assertNotIn(6, visible_ids)

    def test_paginate_by_scope_no_false_match(self):
        """逗号包围格式不会误匹配（如 group_id=1 不应匹配 ',13,'）。"""
        from datas.model.rbac_audit_log import RbacAuditLog
        from app.repositories.rbac_audit_log_repository import RbacAuditLogRepository
        from app.services.pagination import PageQuery

        with self.app.app_context():
            from datas.utils.times import str_to_hms

            tricky = RbacAuditLog(
                id=100, username='tricky', action='user:login',
                resource='tricky', actor_group_ids=',13,',
                create_time=str_to_hms('2026-07-31 11:00:00'),
            )
            self.db.session.add(tricky)
            self.db.session.commit()

            repo = RbacAuditLogRepository(self.db.session)
            pq = PageQuery(page=1, per_page=50)
            page = repo.paginate_by_scope(pq, [1])
            visible_ids = {item.id for item in page.items}
            self.assertNotIn(100, visible_ids)

            page2 = repo.paginate_by_scope(pq, [13])
            visible_ids2 = {item.id for item in page2.items}
            self.assertIn(100, visible_ids2)

    def test_paginate_by_scope_empty_groups_returns_nothing(self):
        """viewer_group_ids 为空 → 不返回任何记录。"""
        from app.repositories.rbac_audit_log_repository import RbacAuditLogRepository
        from app.services.pagination import PageQuery

        with self.app.app_context():
            repo = RbacAuditLogRepository(self.db.session)
            pq = PageQuery(page=1, per_page=50)
            page = repo.paginate_by_scope(pq, [])
            self.assertEqual(len(page.items), 0)

    def test_historical_empty_actor_groups_invisible_to_scoped_admin(self):
        """历史记录（actor_group_ids=''）对按组管理员不可见。"""
        from app.repositories.rbac_audit_log_repository import RbacAuditLogRepository
        from app.services.pagination import PageQuery

        with self.app.app_context():
            repo = RbacAuditLogRepository(self.db.session)
            pq = PageQuery(page=1, per_page=50)
            page = repo.paginate_by_scope(pq, [1, 2, 3, 4])
            visible_ids = {item.id for item in page.items}
            self.assertNotIn(1, visible_ids)
            self.assertNotIn(6, visible_ids)


if __name__ == '__main__':
    unittest.main()
