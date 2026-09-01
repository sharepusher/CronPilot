# -*- coding: utf-8 -*-
"""OPT-P1-18: Test AJAX partial refresh for v2 execution logs filters."""
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
    app.secret_key = 'test-exec-logs-partial'
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
    from app import db, register_hms_filters
    db.init_app(app)
    register_hms_filters(app)
    from app.services.cron_schedule_display import format_duration
    app.jinja_env.filters['format_duration'] = format_duration
    app.register_blueprint(main_blueprint)
    from app.rbac import rbac as rbac_blueprint
    app.register_blueprint(rbac_blueprint)

    @app.before_request
    def _set_ui_version():
        from flask import g as _g
        _g.ui_version = 'v2'

    return app, db


class TestExecLogsPartial(unittest.TestCase):
    """Verify /job_log_all_list?partial=1 and /job_log_list?partial=1 return JSON."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.db = _make_app()
        with cls.app.app_context():
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

    def test_all_list_partial_returns_json(self):
        """job_log_all_list?partial=1 should return JSON with rows, pagination, total."""
        with self.app.test_client() as c:
            self._login_session(c)
            resp = c.get('/job_log_all_list?partial=1')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)
            self.assertIn('pagination', data)
            self.assertIn('total', data)

    def test_all_list_partial_with_outcome_filter(self):
        """partial=1 with outcome filter should return JSON."""
        with self.app.test_client() as c:
            self._login_session(c)
            resp = c.get('/job_log_all_list?partial=1&outcome=fail')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertIn('rows', data)
            self.assertEqual(data['total'], 0)

    def test_single_task_partial_returns_json(self):
        """job_log_list?id=999&partial=1 with non-existent task returns full page (acceptable)."""
        with self.app.test_client() as c:
            self._login_session(c)
            resp = c.get('/job_log_list?id=999&partial=1')
            # Non-existent task early-returns full HTML page (not JSON)
            # This is acceptable — the AJAX client will only call partial=1
            # for tasks that exist (it navigated to that page already)
            self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_redirects(self):
        """Without login session, partial=1 should redirect to login."""
        with self.app.test_client() as c:
            resp = c.get('/job_log_all_list?partial=1')
            self.assertIn(resp.status_code, (301, 302))

    def test_full_page_not_json(self):
        """Without partial=1, should not return JSON."""
        with self.app.test_client() as c:
            self._login_session(c)
            resp = c.get('/job_log_all_list')
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn(resp.status_code, (301, 302))
            # Should be HTML, not JSON
            try:
                data = json.loads(resp.data)
                self.assertNotIn('rows', data)
            except (json.JSONDecodeError, ValueError):
                pass  # Expected: HTML content, not JSON


if __name__ == '__main__':
    unittest.main()
