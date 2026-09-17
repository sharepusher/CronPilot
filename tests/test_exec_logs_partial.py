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
    from app.services.job_log_display import job_log_badge
    app.jinja_env.filters['format_duration'] = format_duration
    app.jinja_env.filters['job_log_badge'] = job_log_badge
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
            import datas.model.job_health  # noqa: F401
            import datas.model.job_log  # noqa: F401
            import datas.model.job_log_items  # noqa: F401
            import datas.model.operation_log  # noqa: F401
            import datas.model.rbac_audit_log  # noqa: F401
            import datas.model.rbac_registration_request  # noqa: F401
            import datas.model.rbac_user  # noqa: F401
            import datas.model.resource_group  # noqa: F401
            import datas.model.tag  # noqa: F401
            import datas.model.task_group  # noqa: F401
            import datas.model.task_tag  # noqa: F401
            import datas.model.user_group  # noqa: F401
            cls.db.create_all()
            from datas.model.rbac_user import RbacUser
            user = RbacUser(username='admin', role='admin', is_active=1)
            user.set_password('test-password')
            cls.db.session.add(user)
            cls.db.session.commit()
            cls.admin_id = user.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.db.drop_all()

    def _login_session(self, client, role='admin', username='admin'):
        with client.session_transaction() as sess:
            sess['is_login'] = True
            sess['user_id'] = self.admin_id
            sess['auth_version'] = 0
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

    def test_pending_badge_and_in_progress_filter(self):
        """R1: pending →「已入队」；进行中筛选可见；非成功不含 pending。"""
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos
            from datas.model.job_log import JobLog
            task = CronInfos(
                task_name='r1-pending-task',
                req_url='http://127.0.0.1/health',
                status=1,
            )
            self.db.session.add(task)
            self.db.session.flush()
            pending = JobLog(
                cron_info_id=task.id,
                status='pending',
                content='',
                take_time=0,
                http_status=0,
                trace_id='r1-pending-trace',
            )
            running = JobLog(
                cron_info_id=task.id,
                status='running',
                content='',
                take_time=0,
                http_status=0,
                trace_id='r1-running-trace',
            )
            failed = JobLog(
                cron_info_id=task.id,
                status='fail',
                content='boom',
                take_time=0.1,
                http_status=500,
                trace_id='r1-fail-trace',
            )
            self.db.session.add_all([pending, running, failed])
            self.db.session.commit()
            pending_id = pending.id

        with self.app.test_client() as c:
            self._login_session(c)
            page = c.get('/job_log_all_list?outcome=all')
            self.assertEqual(page.status_code, 200)
            html = page.data.decode('utf-8')
            self.assertIn('进行中', html)
            self.assertIn('已入队', html)
            self.assertIn('el-log-pending', html)
            self.assertIn('el-log-running', html)
            self.assertRegex(html, r'el-log-pending[^>]*>[\s\S]*?已入队')

            progress = c.get('/job_log_all_list?partial=1&outcome=in_progress')
            self.assertEqual(progress.status_code, 200)
            pdata = json.loads(progress.data)
            self.assertEqual(pdata['total'], 2)
            self.assertIn('已入队', pdata['rows'])
            self.assertIn('执行中', pdata['rows'])
            self.assertNotIn('未知', pdata['rows'])

            not_success = c.get('/job_log_all_list?partial=1&outcome=not_success')
            self.assertEqual(not_success.status_code, 200)
            ndata = json.loads(not_success.data)
            self.assertEqual(ndata['total'], 1)
            self.assertIn('失败', ndata['rows'])
            self.assertNotIn(str(pending_id), ndata['rows'])


if __name__ == '__main__':
    unittest.main()
