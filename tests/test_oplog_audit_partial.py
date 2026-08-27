# -*- coding: utf-8 -*-
"""OPT-P1-19: Test AJAX partial refresh for v2 operation log and audit logs."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from flask import Flask

from app.main import main as main_blueprint
from app.rbac import rbac as rbac_blueprint


def _make_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, 'app', 'templates'),
        static_folder=os.path.join(ROOT, 'app', 'static'),
    )
    app.secret_key = 'test-oplog-audit-partial'
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['CRONPILOT_FORCE_NEW_UI'] = True
    app.config['CRON_CONFIG'] = {
        'is_dev': '0',
        'block_private_ip': '0',
        'url_allow_hosts': '',
        'url_ssrf_observe_only': '1',
    }
    from app import db, register_hms_filters
    db.init_app(app)
    register_hms_filters(app)
    from app.services.cron_schedule_display import format_duration
    app.jinja_env.filters['format_duration'] = format_duration
    app.register_blueprint(main_blueprint)
    app.register_blueprint(rbac_blueprint)

    @app.before_request
    def _set_ui_version():
        from flask import g as _g
        _g.ui_version = 'v2'

    return app, db


class TestOpLogPartial(unittest.TestCase):
    """Verify /operation_log_list?partial=1 returns JSON with rows/pagination/total."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.db = _make_app()
        with cls.app.app_context():
            import datas.model.cron_infos  # noqa: F401
            import datas.model.operation_log  # noqa: F401
            import datas.model.resource_group  # noqa: F401
            import datas.model.rbac_user  # noqa: F401
            import datas.model.tag  # noqa: F401
            cls.db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.db.drop_all()

    def _login(self, c):
        with c.session_transaction() as s:
            s['is_login'] = True
            s['user_id'] = 1
            s['role'] = 'admin'
            s['username'] = 'admin'
            s['group_ids'] = []

    def test_partial_returns_json(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/operation_log_list?partial=1')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)
            self.assertIn('pagination', data)
            self.assertIn('total', data)
            self.assertIsInstance(data['total'], int)

    def test_partial_with_action_filter(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/operation_log_list?partial=1&action=create')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)
            self.assertEqual(data['total'], 0)

    def test_full_page_returns_html(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/operation_log_list')
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b'<!DOCTYPE html', resp.data[:100].lower() + resp.data[:100])


class TestAuditLogPartial(unittest.TestCase):
    """Verify /rbac/audit_logs?partial=1 returns JSON with rows/pagination/total."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.db = _make_app()
        with cls.app.app_context():
            import datas.model.rbac_audit_log  # noqa: F401
            import datas.model.rbac_user  # noqa: F401
            import datas.model.resource_group  # noqa: F401
            cls.db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.db.drop_all()

    def _login(self, c):
        with c.session_transaction() as s:
            s['is_login'] = True
            s['user_id'] = 1
            s['role'] = 'admin'
            s['username'] = 'admin'
            s['group_ids'] = []

    def test_partial_returns_json(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/rbac/audit-logs?partial=1')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)
            self.assertIn('pagination', data)
            self.assertIn('total', data)
            self.assertIsInstance(data['total'], int)

    def test_partial_with_chip_filter(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/rbac/audit-logs?partial=1&chip=login_ok')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)
            self.assertEqual(data['total'], 0)

    def test_partial_with_username_filter(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/rbac/audit-logs?partial=1&username=nonexist')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertEqual(data['total'], 0)

    def test_full_page_returns_html(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/rbac/audit-logs')
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b'<!DOCTYPE html', resp.data[:100].lower() + resp.data[:100])


class TestUsersPartial(unittest.TestCase):
    """Verify /rbac/users?partial=1 returns JSON with rows/pagination/total/counts."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.db = _make_app()
        with cls.app.app_context():
            import datas.model.rbac_user  # noqa: F401
            import datas.model.resource_group  # noqa: F401
            cls.db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.db.drop_all()

    def _login(self, c):
        with c.session_transaction() as s:
            s['is_login'] = True
            s['user_id'] = 1
            s['role'] = 'admin'
            s['username'] = 'admin'
            s['group_ids'] = []

    def test_partial_returns_json(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/rbac/users?partial=1')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)
            self.assertIn('pagination', data)
            self.assertIn('total', data)
            self.assertIn('counts', data)
            self.assertIn('total', data['counts'])
            self.assertIn('active', data['counts'])
            self.assertIn('inactive', data['counts'])

    def test_partial_with_chip_filter(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/rbac/users?partial=1&chip=active')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)

    def test_partial_with_username_filter(self):
        with self.app.test_client() as c:
            self._login(c)
            resp = c.get('/rbac/users?partial=1&username=nonexist')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertEqual(data['total'], 0)


if __name__ == '__main__':
    unittest.main()
