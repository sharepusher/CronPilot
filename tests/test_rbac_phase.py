import os
import unittest
from unittest.mock import patch

from flask import Flask, render_template, session

from app.main import main as main_blueprint
from app.rbac.context import make_has_perm
from app.rbac.policy import has_permission
from app.rbac.services import get_rbac_enabled, get_role_permission_set


class TestCheckPassForward(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(main_blueprint)
        self.client = app.test_client()

    def _location_path_query(self, resp):
        loc = resp.headers['Location']
        if loc.startswith('http://') or loc.startswith('https://'):
            from urllib.parse import urlparse
            parsed = urlparse(loc)
            return parsed.path + (('?' + parsed.query) if parsed.query else '')
        return loc

    def test_get_without_next_redirects_to_rbac_login(self):
        resp = self.client.get('/check_pass')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._location_path_query(resp), '/rbac/login')

    def test_get_with_next_passthrough_matches_decorator_format(self):
        resp = self.client.get('/check_pass?next=/cron_list?task_name=x')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            self._location_path_query(resp),
            '/rbac/login?next=/cron_list?task_name=x',
        )

    def test_post_without_next_uses_307(self):
        resp = self.client.post('/check_pass')
        self.assertEqual(resp.status_code, 307)
        self.assertEqual(self._location_path_query(resp), '/rbac/login')

    def test_post_with_next_passthrough_matches_decorator_format(self):
        resp = self.client.post('/check_pass?next=/cron_list')
        self.assertEqual(resp.status_code, 307)
        self.assertEqual(self._location_path_query(resp), '/rbac/login?next=/cron_list')


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestRbacLogin(unittest.TestCase):
    def setUp(self):
        get_rbac_enabled.cache_clear()
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        with app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            db.create_all()

    def tearDown(self):
        get_rbac_enabled.cache_clear()

    def test_login_get_renders(self):
        resp = self.client.get('/rbac/login')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('密码', resp.get_data(as_text=True))

    def test_seed_admin_login_redirects_to_next(self):
        with patch(
            'app.rbac.services.configs',
            return_value={'login_pwd': 'changeme', 'rbac_enable': '0'},
        ):
            get_rbac_enabled.cache_clear()
            resp = self.client.post(
                '/rbac/login',
                data={
                    'username': 'admin',
                    'password': 'changeme',
                    'next': '/cron_list?task_name=x',
                },
            )
            self.assertEqual(resp.status_code, 302)
            self.assertIn('/cron_list?task_name=x', resp.headers['Location'])

    def test_empty_username_rejected(self):
        with patch(
            'app.rbac.services.configs',
            return_value={'login_pwd': 'changeme', 'rbac_enable': '0'},
        ):
            get_rbac_enabled.cache_clear()
            resp = self.client.post(
                '/rbac/login',
                data={'password': 'changeme', 'next': '/cron_list'},
                follow_redirects=False,
            )
            self.assertEqual(resp.status_code, 302)
            self.assertIn('msg=', resp.headers['Location'])
            from urllib.parse import unquote
            self.assertIn('用户名', unquote(resp.headers['Location']))



    def test_check_pass_forwards_next_to_login(self):
        resp = self.client.get('/check_pass?next=/cron_list?task_name=x')
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers['Location']
        self.assertIn('/rbac/login?next=', loc)
        self.assertIn('task_name=x', loc)


class TestR3Permissions(unittest.TestCase):
    def setUp(self):
        get_rbac_enabled.cache_clear()
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        with app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            db.create_all()

    def tearDown(self):
        get_rbac_enabled.cache_clear()

    def _login_as(self, role):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = role

    def test_viewer_cron_write_routes_return_403(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            self._login_as('viewer')
            for path in ('/cron_add', '/cron_edit?id=1', '/update_status?id=1'):
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 403, path)

    def test_viewer_log_delete_returns_410(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            self._login_as('viewer')
            resp = self.client.post('/job_log_delete', data={'job_log_id': '1'})
            self.assertEqual(resp.status_code, 410)
            resp = self.client.post('/job_batch_delete', data={'id': '1'})
            self.assertEqual(resp.status_code, 410)

    def test_viewer_cron_retire_returns_403(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            self._login_as('viewer')
            resp = self.client.get('/cron_retire?id=1')
            self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_redirects_to_rbac_login_with_next(self):
        resp = self.client.get('/cron_list')
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers['Location']
        self.assertIn('/rbac/login?next=', loc)
        self.assertIn('/cron_list', loc)


class TestLifecycleNoDelete(unittest.TestCase):
    def setUp(self):
        get_rbac_enabled.cache_clear()
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.client = app.test_client()

    def tearDown(self):
        get_rbac_enabled.cache_clear()

    def test_operator_cron_del_returns_410(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with self.client.session_transaction() as sess:
                sess['is_login'] = True
                sess['role'] = 'operator'
            resp = self.client.post('/cron_batch_del', data={'id': '1'})
            self.assertEqual(resp.status_code, 410)
            resp = self.client.get('/cron_del?id=1')
            self.assertEqual(resp.status_code, 410)

    def test_operator_cannot_retire(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with self.client.session_transaction() as sess:
                sess['is_login'] = True
                sess['role'] = 'operator'
            resp = self.client.get('/cron_retire?id=1')
            self.assertEqual(resp.status_code, 403)

    def test_admin_retire_requires_reason_and_writes_fields(self):
        from app import db
        from datas.model.cron_infos import CronInfos

        with self.client.application.app_context():
            db.create_all()
            cif = CronInfos(
                task_name='retire-me',
                task_keyword='说明',
                req_url='https://example.com/x',
                status=1,
                created_at='2026-01-01 00:00:00',
                updated_at='2026-01-01 00:00:00',
            )
            db.session.add(cif)
            db.session.commit()
            cron_id = cif.id

        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with patch('app.services.cron_service.scheduler') as sch:
                sch.remove_job.side_effect = Exception('no job')
                with self.client.session_transaction() as sess:
                    sess['is_login'] = True
                    sess['role'] = 'admin'
                resp = self.client.post(
                    '/cron_retire',
                    data={'id': str(cron_id)},
                )
                self.assertEqual(resp.status_code, 200)
                payload = resp.get_json()
                self.assertEqual(payload.get('errmsg'), '请填写下线原因')

                resp = self.client.post(
                    '/cron_retire',
                    data={'id': str(cron_id), 'reason': '测试下线'},
                )
                self.assertEqual(resp.status_code, 200)

        with self.client.application.app_context():
            row = db.session.get(CronInfos, cron_id)
            self.assertEqual(row.status, -1)
            self.assertEqual(row.retire_reason, '测试下线')
            self.assertTrue(row.retired_at)


class TestNavHasPerm(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app

    def _render_nav(self, role, rbac_enabled=True):
        with self.app.app_context():
            with self.app.test_request_context():
                session['is_login'] = True
                session['role'] = role
                with patch('app.rbac.context.get_rbac_enabled', return_value=rbac_enabled):
                    with patch('app.rbac.services.get_rbac_enabled', return_value=rbac_enabled):
                        return render_template('rbac/_nav.html', active='cron_list')

    def test_viewer_nav_hides_cron_add(self):
        html = self._render_nav('viewer')
        self.assertIn('任务列表', html)
        self.assertIn('任务执行记录', html)
        self.assertNotIn('任务添加', html)
        self.assertNotIn('用户管理', html)

    def test_operator_nav_shows_cron_add(self):
        html = self._render_nav('operator')
        self.assertIn('任务添加', html)
        self.assertNotIn('用户管理', html)

    def test_admin_nav_shows_users_when_rbac_on(self):
        html = self._render_nav('admin', rbac_enabled=True)
        self.assertIn('用户管理', html)
        self.assertIn('审计', html)

    def test_admin_nav_hides_users_when_rbac_off(self):
        html = self._render_nav('admin', rbac_enabled=False)
        self.assertNotIn('用户管理', html)
        self.assertNotIn('审计', html)

    def test_operator_nav_hides_audit(self):
        html = self._render_nav('operator', rbac_enabled=True)
        self.assertNotIn('审计', html)


class TestNotFound(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.client = app.test_client()

    def test_guest_404_renders_minimal_page(self):
        resp = self.client.get('/__no_such_route__')
        self.assertEqual(resp.status_code, 404)
        body = resp.get_data(as_text=True)
        self.assertIn('页面不存在', body)
        self.assertIn('前往登录', body)
        self.assertNotIn('任务列表', body)

    def test_logged_in_404_renders_nav_and_home_link(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
        resp = self.client.get('/__no_such_route__')
        self.assertEqual(resp.status_code, 404)
        body = resp.get_data(as_text=True)
        self.assertIn('页面不存在', body)
        self.assertIn('返回任务列表', body)
        self.assertIn('任务列表', body)


class TestRbacUsersManage(unittest.TestCase):
    def setUp(self):
        get_rbac_enabled.cache_clear()
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            db.create_all()

    def tearDown(self):
        get_rbac_enabled.cache_clear()

    def _login(self, role='admin', user_id=None):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = role
            sess['username'] = role
            if user_id is not None:
                sess['user_id'] = user_id

    def test_operator_users_list_403(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with patch('app.rbac.views.get_rbac_enabled', return_value=True):
                self._login('operator')
                resp = self.client.get('/rbac/users')
                self.assertEqual(resp.status_code, 403)

    def test_rbac_off_users_redirects_even_for_admin(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=False):
            with patch('app.rbac.views.get_rbac_enabled', return_value=False):
                self._login('admin')
                resp = self.client.get('/rbac/users')
                self.assertEqual(resp.status_code, 302)
                self.assertIn('/cron_list', resp.headers['Location'])

    def test_admin_create_and_list_users(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with patch('app.rbac.views.get_rbac_enabled', return_value=True):
                with patch('app.rbac.services.get_rbac_enabled', return_value=True):
                    self._login('admin')
                    resp = self.client.post(
                        '/rbac/users/add',
                        data={'username': 'alice', 'password': 'secret', 'role': 'viewer'},
                        headers={'X-Requested-With': 'XMLHttpRequest'},
                    )
                    self.assertEqual(resp.status_code, 200)
                    payload = resp.get_json()
                    self.assertEqual(payload.get('errcode'), 0)
                    self.assertEqual(payload.get('url'), '/rbac/users')
                    resp = self.client.get('/rbac/users')
                    self.assertEqual(resp.status_code, 200)
                    self.assertIn('alice', resp.get_data(as_text=True))

    def test_add_form_has_ajax_submit_button(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with patch('app.rbac.views.get_rbac_enabled', return_value=True):
                with patch('app.rbac.services.get_rbac_enabled', return_value=True):
                    self._login('admin')
                    resp = self.client.get('/rbac/users/add')
                    body = resp.get_data(as_text=True)
                    self.assertIn('js-ajax-form', body)
                    self.assertIn('js-ajax-submit', body)

    def test_native_post_add_redirects_to_list(self):
        """无 Ajax 头时成功应 302 回列表，避免浏览器落在裸 JSON 页。"""
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with patch('app.rbac.views.get_rbac_enabled', return_value=True):
                with patch('app.rbac.services.get_rbac_enabled', return_value=True):
                    self._login('admin')
                    resp = self.client.post(
                        '/rbac/users/add',
                        data={'username': 'bob', 'password': 'secret', 'role': 'viewer'},
                    )
                    self.assertEqual(resp.status_code, 302)
                    self.assertIn('/rbac/users', resp.headers['Location'])

    def test_cannot_disable_last_admin(self):
        from datas.model.rbac_user import RbacUser

        with self.app.app_context():
            admin = RbacUser(username='solo', role='admin', is_active=1, create_time='t')
            admin.set_password('x')
            self.db.session.add(admin)
            self.db.session.commit()
            admin_id = admin.id

        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with patch('app.rbac.views.get_rbac_enabled', return_value=True):
                with patch('app.rbac.services.get_rbac_enabled', return_value=True):
                    self._login('admin', user_id=999)
                    resp = self.client.post(
                        '/rbac/users/edit',
                        data={'id': str(admin_id), 'role': 'viewer', 'is_active': '1'},
                        headers={'X-Requested-With': 'XMLHttpRequest'},
                    )
                    self.assertEqual(resp.status_code, 200)
                    self.assertIn('最后一名', resp.get_json().get('errmsg', ''))

    def test_cannot_disable_self(self):
        from datas.model.rbac_user import RbacUser

        with self.app.app_context():
            a1 = RbacUser(username='a1', role='admin', is_active=1, create_time='t')
            a1.set_password('x')
            a2 = RbacUser(username='a2', role='admin', is_active=1, create_time='t')
            a2.set_password('x')
            self.db.session.add_all([a1, a2])
            self.db.session.commit()
            self_id = a1.id

        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with patch('app.rbac.views.get_rbac_enabled', return_value=True):
                with patch('app.rbac.services.get_rbac_enabled', return_value=True):
                    self._login('admin', user_id=self_id)
                    resp = self.client.post(
                        '/rbac/users/edit',
                        data={'id': str(self_id), 'role': 'admin', 'is_active': '0'},
                        headers={'X-Requested-With': 'XMLHttpRequest'},
                    )
                    self.assertEqual(resp.status_code, 200)
                    self.assertIn('当前登录', resp.get_json().get('errmsg', ''))


class TestRbacAuditLogs(unittest.TestCase):
    def setUp(self):
        get_rbac_enabled.cache_clear()
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            db.create_all()

    def tearDown(self):
        get_rbac_enabled.cache_clear()

    def _login(self, role='admin'):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = role
            sess['username'] = role

    def test_operator_audit_logs_403(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with patch('app.rbac.views.get_rbac_enabled', return_value=True):
                self._login('operator')
                resp = self.client.get('/rbac/audit-logs')
                self.assertEqual(resp.status_code, 403)

    def test_rbac_off_audit_redirects(self):
        with patch('app.rbac.decorators.get_rbac_enabled', return_value=False):
            with patch('app.rbac.views.get_rbac_enabled', return_value=False):
                self._login('admin')
                resp = self.client.get('/rbac/audit-logs')
                self.assertEqual(resp.status_code, 302)
                self.assertIn('/cron_list', resp.headers['Location'])

    def test_admin_lists_audit_rows(self):
        from datas.model.rbac_audit_log import RbacAuditLog

        with self.app.app_context():
            self.db.session.add(
                RbacAuditLog(
                    username='admin',
                    user_id=1,
                    action='user:login',
                    resource='admin',
                    ip='127.0.0.1',
                    status='allow',
                    create_time='2026-07-14 10:00:00',
                )
            )
            self.db.session.commit()

        with patch('app.rbac.decorators.get_rbac_enabled', return_value=True):
            with patch('app.rbac.views.get_rbac_enabled', return_value=True):
                with patch('app.rbac.services.get_rbac_enabled', return_value=True):
                    self._login('admin')
                    resp = self.client.get('/rbac/audit-logs')
                    self.assertEqual(resp.status_code, 200)
                    body = resp.get_data(as_text=True)
                    self.assertIn('登录', body)
                    self.assertIn('用户 ID', body)
                    self.assertIn('账号 admin', body)
                    self.assertIn('<td>1</td>', body)
                    self.assertNotIn('js-ajax-form', body)
                    self.assertNotIn('legacy_admin', body)

    def test_audit_labels_unit(self):
        from app.rbac.services import (
            audit_action_label,
            audit_resource_label,
            audit_status_label,
        )
        self.assertEqual(audit_action_label('user:login'), '登录')
        self.assertEqual(audit_status_label('deny'), '拒绝')
        self.assertEqual(
            audit_resource_label('permission:deny', 'user:manage'),
            '缺少权限 user:manage',
        )
        self.assertEqual(audit_action_label('unknown:x'), 'unknown:x')


class TestRbacPolicy(unittest.TestCase):
    def test_viewer_cannot_write(self):
        self.assertFalse(has_permission('viewer', 'cron:write'))

    def test_operator_cannot_retire_cron(self):
        self.assertFalse(has_permission('operator', 'cron:retire'))

    def test_admin_has_retire(self):
        self.assertTrue(has_permission('admin', 'cron:retire'))

    def test_admin_has_user_manage(self):
        self.assertTrue(has_permission('admin', 'user:manage'))

    def test_admin_has_audit_read(self):
        self.assertTrue(has_permission('admin', 'audit:read'))

    def test_no_delete_permissions(self):
        self.assertFalse(has_permission('admin', 'cron:delete'))
        self.assertFalse(has_permission('operator', 'log:delete'))


class TestMakeHasPerm(unittest.TestCase):
    def setUp(self):
        get_rbac_enabled.cache_clear()

    def tearDown(self):
        get_rbac_enabled.cache_clear()

    def test_rbac_disabled_always_true(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        with app.test_request_context():
            with patch('app.rbac.context.get_rbac_enabled', return_value=False) as mocked:
                has_perm = make_has_perm()
                for _ in range(200):
                    self.assertTrue(has_perm('cron:retire'))
                mocked.assert_called_once()

    def test_rbac_enabled_uses_preloaded_set(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        with app.test_request_context():
            session['role'] = 'viewer'
            with patch('app.rbac.context.get_rbac_enabled', return_value=True) as mocked_enabled:
                with patch('app.rbac.context.get_role_permission_set', return_value={'cron:read'}) as mocked_perms:
                    has_perm = make_has_perm()
                    self.assertTrue(has_perm('cron:read'))
                    self.assertFalse(has_perm('cron:write'))
                    for _ in range(198):
                        has_perm('cron:read')
                    mocked_enabled.assert_called_once()
                    mocked_perms.assert_called_once_with('viewer')

    def test_get_rbac_enabled_uses_process_cache(self):
        get_rbac_enabled.cache_clear()
        with patch('app.rbac.services.configs', return_value={'rbac_enable': '1'}) as mocked:
            self.assertTrue(get_rbac_enabled())
            self.assertTrue(get_rbac_enabled())
            mocked.assert_called_once()
        get_rbac_enabled.cache_clear()

        perms = get_role_permission_set('admin')
        self.assertIn('user:manage', perms)
        self.assertEqual(perms, get_role_permission_set('admin'))


if __name__ == '__main__':
    unittest.main()
