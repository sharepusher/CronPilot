# -*- coding:utf-8 -*-
"""OPT-P2-12 Resource Scope 单测。"""
import os
import unittest
from types import SimpleNamespace

from flask import Flask

from app.rbac.authorize import AuthorizationError, authorize
from app.rbac.policy import has_permission, role_bypasses_scope
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
        err, st, gid = normalize_scope_fields('GLOBAL', 99)
        self.assertIsNone(err)
        self.assertEqual(st, SCOPE_GLOBAL)
        self.assertIsNone(gid)

    def test_normalize_group_requires_id(self):
        err, st, gid = normalize_scope_fields('GROUP', '')
        self.assertIsNotNone(err)
        err, st, gid = normalize_scope_fields('GROUP', 3)
        self.assertIsNone(err)
        self.assertEqual(st, SCOPE_GROUP)
        self.assertEqual(gid, 3)

    def test_has_scope_matrix(self):
        glob = SimpleNamespace(scope_type='GLOBAL', group_id=None, id=1)
        ga = SimpleNamespace(scope_type='GROUP', group_id=1, id=2)
        gb = SimpleNamespace(scope_type='GROUP', group_id=2, id=3)
        self.assertTrue(has_scope('viewer', [1], glob))
        self.assertTrue(has_scope('viewer', [1], ga))
        self.assertFalse(has_scope('viewer', [1], gb))
        self.assertTrue(has_scope('admin', [], gb))
        self.assertFalse(has_scope('operator', [], ga))

    def test_user_can_assign_group(self):
        self.assertTrue(user_can_assign_group('admin', [], 9))
        self.assertTrue(user_can_assign_group('operator', [1, 2], 1))
        self.assertFalse(user_can_assign_group('operator', [1], 2))

    def test_build_scope_filter_admin_none(self):
        self.assertIsNone(build_scope_filter_clause('admin', []))

    def test_authorize_permission_then_scope(self):
        other = SimpleNamespace(scope_type='GROUP', group_id=2, id=9)
        with self.assertRaises(AuthorizationError) as cm:
            authorize('viewer', 'cron:write', other, group_ids=[1])
        self.assertEqual(cm.exception.kind, 'permission')
        with self.assertRaises(AuthorizationError) as cm2:
            authorize('operator', 'cron:write', other, group_ids=[1])
        self.assertEqual(cm2.exception.kind, 'scope')
        authorize('admin', 'cron:write', other, group_ids=[])
        authorize('operator', 'cron:write', SimpleNamespace(scope_type='GLOBAL', group_id=None, id=1), group_ids=[])


class TestGroupCodeAndMembership(unittest.TestCase):
    def test_slugify_english(self):
        from app.rbac.group_code import generate_group_code, slugify_code

        self.assertEqual(slugify_code('Biz Line A'), 'biz-line-a')
        self.assertEqual(
            generate_group_code('Platform Ops', translate=False),
            'platform-ops',
        )

    def test_unique_suffix(self):
        from app.rbac.group_code import generate_group_code

        code = generate_group_code('demo', existing_codes={'demo'}, translate=False)
        self.assertEqual(code, 'demo-2')

    def test_html_entity_in_translation(self):
        from app.rbac.group_code import generate_group_code, slugify_code

        self.assertEqual(slugify_code('R&D Center'), 'r-d-center')
        from app.rbac import group_code as gc
        orig = gc.translate_to_english
        gc.translate_to_english = lambda text, timeout=3.0: 'R&amp;D Center'
        try:
            self.assertEqual(gc.generate_group_code('研发', translate=True), 'r-d-center')
        finally:
            gc.translate_to_english = orig

    def test_non_admin_requires_groups(self):
        from app.rbac.services import validate_groups_for_role

        self.assertEqual(validate_groups_for_role('admin', []), '')
        self.assertIn('必须', validate_groups_for_role('viewer', []))
        self.assertIn('必须', validate_groups_for_role('operator', []))
        self.assertEqual(validate_groups_for_role('operator', [1]), '')


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
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            db.create_all()
            self._seed()

    def _seed(self):
        from datas.model.cron_infos import CronInfos
        from datas.model.rbac_user import RbacUser
        from datas.model.resource_group import ResourceGroup
        from datas.model.user_group import UserGroup
        from datas.utils.times import get_now_time

        g1 = ResourceGroup(name='组A', code='biz-a', description='', create_time=get_now_time())
        g2 = ResourceGroup(name='组B', code='biz-b', description='', create_time=get_now_time())
        self.db.session.add_all([g1, g2])
        self.db.session.flush()
        self.g1_id = g1.id
        self.g2_id = g2.id

        op = RbacUser(username='op_a', role='operator', is_active=1, create_time=get_now_time())
        op.set_password('pass')
        vw = RbacUser(username='vw_a', role='viewer', is_active=1, create_time=get_now_time())
        vw.set_password('pass')
        adm = RbacUser(username='adm', role='admin', is_active=1, create_time=get_now_time())
        adm.set_password('pass')
        self.db.session.add_all([op, vw, adm])
        self.db.session.flush()
        self.db.session.add(UserGroup(user_id=op.id, group_id=g1.id))
        self.db.session.add(UserGroup(user_id=vw.id, group_id=g1.id))

        now = get_now_time()
        c_global = CronInfos(
            task_name='global_task',
            task_keyword='kw',
            req_url='https://example.com/g',
            status=1,
            created_at=now,
            updated_at=now,
            scope_type='GLOBAL',
            group_id=None,
        )
        c_a = CronInfos(
            task_name='group_a_task',
            task_keyword='kw',
            req_url='https://example.com/a',
            status=1,
            created_at=now,
            updated_at=now,
            scope_type='GROUP',
            group_id=g1.id,
        )
        c_b = CronInfos(
            task_name='group_b_task',
            task_keyword='kw',
            req_url='https://example.com/b',
            status=1,
            created_at=now,
            updated_at=now,
            scope_type='GROUP',
            group_id=g2.id,
        )
        self.db.session.add_all([c_global, c_a, c_b])
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

        with self.app.app_context():
            cif = self.db.session.get(CronInfos, self.global_id)
            self.assertEqual(cif.scope_type, 'GLOBAL')
            self.assertIsNone(cif.group_id)


if __name__ == '__main__':
    unittest.main()
