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
