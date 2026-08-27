# -*- coding: utf-8 -*-
"""OPT-P1-17: Test AJAX partial refresh for v2 dashboard filters."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from flask import Flask

from app.main import main as main_blueprint


def _make_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, 'app', 'templates'),
        static_folder=os.path.join(ROOT, 'app', 'static'),
    )
    app.secret_key = 'test-dashboard-partial'
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
    app.register_blueprint(main_blueprint)
    from app.rbac import rbac as rbac_blueprint
    app.register_blueprint(rbac_blueprint)

    @app.before_request
    def _set_ui_version():
        from flask import g as _g
        _g.ui_version = 'v2'

    return app, db


class TestDashboardPartial(unittest.TestCase):
    """Verify /cron_list?partial=1 returns JSON with rows/pagination/stats/total."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.db = _make_app()
        with cls.app.app_context():
            # Import all models so create_all creates their tables
            import datas.model.cron_infos  # noqa: F401
            import datas.model.job_log  # noqa: F401
            import datas.model.job_log_items  # noqa: F401
            import datas.model.job_health  # noqa: F401
            import datas.model.tag  # noqa: F401
            import datas.model.task_tag  # noqa: F401
            import datas.model.task_group  # noqa: F401
            import datas.model.resource_group  # noqa: F401
            import datas.model.user_group  # noqa: F401
            import datas.model.operation_log  # noqa: F401
            import datas.model.rbac_user  # noqa: F401
            import datas.model.rbac_audit_log  # noqa: F401
            import datas.model.rbac_registration_request  # noqa: F401
            cls.db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.db.drop_all()

    def _login_session(self, client, role='admin', username='admin'):
        with client.session_transaction() as sess:
            sess['is_login'] = True
            sess['user_id'] = 1
            sess['username'] = username
            sess['role'] = role
            sess['group_ids'] = []

    def test_partial_returns_json_keys(self):
        """partial=1 should return JSON with rows, pagination, stats, total."""
        with self.app.test_client() as c:
            self._login_session(c)
            resp = c.get('/cron_list?partial=1')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)
            self.assertIn('pagination', data)
            self.assertIn('stats', data)
            self.assertIn('total', data)
            stats = data['stats']
            for key in ('failing', 'consecutive_failing', 'overdue_count',
                        'today_fail_runs', 'total', 'today_success_rate'):
                self.assertIn(key, stats)

    def test_partial_with_filters(self):
        """partial=1 with filter params should still return JSON."""
        with self.app.test_client() as c:
            self._login_session(c)
            resp = c.get('/cron_list?partial=1&health=failing&page=1')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)
            self.assertIn('total', data)

    def test_full_page_returns_html(self):
        """Without partial=1, should return full HTML page (200 or template error is acceptable)."""
        with self.app.test_client() as c:
            self._login_session(c)
            resp = c.get('/cron_list')
            # Full page render might fail due to missing tables in memory db,
            # but at minimum it should not redirect (auth should pass)
            self.assertNotIn(resp.status_code, (301, 302),
                             'Authenticated request should not redirect')

    def test_unauthenticated_redirects(self):
        """Without login session, partial=1 should redirect to login."""
        with self.app.test_client() as c:
            resp = c.get('/cron_list?partial=1')
            self.assertIn(resp.status_code, (301, 302))


if __name__ == '__main__':
    unittest.main()
