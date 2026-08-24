"""Tests for logout CSRF protection (S1 + S2 security fix).

Verifies:
- /rbac/logout rejects GET (405)
- /rbac/logout accepts POST (302 redirect to login)
- Legacy /logout and /check_pass redirect to /rbac/login
"""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask


class TestLogoutCSRF(unittest.TestCase):

    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
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
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_get_logout_returns_405(self):
        """GET /rbac/logout must be rejected (Method Not Allowed)."""
        resp = self.client.get('/rbac/logout')
        self.assertEqual(resp.status_code, 405)

    def test_post_logout_redirects(self):
        """POST /rbac/logout clears session and redirects to login."""
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['username'] = 'testuser'
        resp = self.client.post('/rbac/logout')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/rbac/login', resp.headers['Location'])
        with self.client.session_transaction() as sess:
            self.assertNotIn('is_login', sess)

    def test_legacy_logout_redirects_to_login(self):
        """GET /logout (legacy) redirects to /rbac/login."""
        resp = self.client.get('/logout')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/rbac/login', resp.headers['Location'])

    def test_legacy_check_pass_redirects_to_login(self):
        """GET /check_pass (legacy) redirects to /rbac/login."""
        resp = self.client.get('/check_pass')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/rbac/login', resp.headers['Location'])


if __name__ == '__main__':
    unittest.main()
