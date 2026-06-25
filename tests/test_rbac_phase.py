import os
import unittest
from unittest.mock import patch

from flask import Flask, session

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

    def test_legacy_login_redirects_to_next(self):
        with patch('app.rbac.services.configs', return_value={'login_pwd': 'changeme', 'rbac_enable': '0'}):
            get_rbac_enabled.cache_clear()
            resp = self.client.post(
                '/rbac/login',
                data={'password': 'changeme', 'next': '/cron_list?task_name=x'},
            )
            self.assertEqual(resp.status_code, 302)
            self.assertIn('/cron_list?task_name=x', resp.headers['Location'])

    def test_check_pass_forwards_next_to_login(self):
        resp = self.client.get('/check_pass?next=/cron_list?task_name=x')
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers['Location']
        self.assertIn('/rbac/login?next=', loc)
        self.assertIn('task_name=x', loc)


class TestRbacPolicy(unittest.TestCase):
    def test_viewer_cannot_write(self):
        self.assertFalse(has_permission('viewer', 'cron:write'))

    def test_operator_cannot_delete_cron(self):
        self.assertFalse(has_permission('operator', 'cron:delete'))

    def test_admin_has_user_manage(self):
        self.assertTrue(has_permission('admin', 'user:manage'))


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
                    self.assertTrue(has_perm('cron:delete'))
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
