# -*- coding:utf-8 -*-
"""任务列表「立即执行」接口。"""
import os
import unittest
from unittest.mock import patch

from flask import Flask

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

from app.main.views import main as main_blueprint


class TestCronRunNow(unittest.TestCase):
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
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.cron_infos import CronInfos
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            db.create_all()
            self.active = CronInfos(
                task_name='run-now-ok',
                task_keyword='说明',
                req_url='https://example.com/run',
                status=1,
                created_at='t',
                updated_at='t',
            )
            self.retired = CronInfos(
                task_name='run-now-retired',
                task_keyword='说明',
                req_url='https://example.com/old',
                status=-1,
                created_at='t',
                updated_at='t',
            )
            self.no_url = CronInfos(
                task_name='run-now-empty',
                task_keyword='说明',
                req_url='',
                status=1,
                created_at='t',
                updated_at='t',
            )
            db.session.add_all([self.active, self.retired, self.no_url])
            db.session.commit()
            self.active_id = self.active.id
            self.retired_id = self.retired.id
            self.no_url_id = self.no_url.id

    def _login_admin(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'admin'
            sess['username'] = 'ops_admin'
            sess['group_ids'] = []

    @patch('app.crons.cron_do', return_value=42)
    def test_admin_run_now_success(self, mock_do):
        self._login_admin()
        resp = self.client.post('/cron_run_now?id=%s' % self.active_id)
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload.get('errcode'), 0)
        self.assertIn('/job_log_detail?id=42', payload.get('url') or '')
        mock_do.assert_called_once_with(self.active_id)

    def test_retired_task_rejected(self):
        self._login_admin()
        resp = self.client.post('/cron_run_now?id=%s' % self.retired_id)
        payload = resp.get_json()
        self.assertEqual(payload.get('errcode'), 1)
        self.assertIn('下线', payload.get('errmsg') or '')

    def test_paused_task_rejected(self):
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos
            paused = CronInfos(
                task_name='run-now-paused',
                task_keyword='说明',
                req_url='https://example.com/paused',
                status=0,
                created_at='t',
                updated_at='t',
            )
            self.db.session.add(paused)
            self.db.session.commit()
            paused_id = paused.id
        self._login_admin()
        resp = self.client.post('/cron_run_now?id=%s' % paused_id)
        payload = resp.get_json()
        self.assertEqual(payload.get('errcode'), 1)
        self.assertIn('运行中', payload.get('errmsg') or '')

    def test_missing_url_rejected(self):
        self._login_admin()
        resp = self.client.post('/cron_run_now?id=%s' % self.no_url_id)
        payload = resp.get_json()
        self.assertEqual(payload.get('errcode'), 1)
        self.assertIn('URL', payload.get('errmsg') or '')

    @patch('app.crons.cron_do', return_value=None)
    def test_busy_task_rejected(self, _mock_do):
        self._login_admin()
        resp = self.client.post('/cron_run_now?id=%s' % self.active_id)
        payload = resp.get_json()
        self.assertEqual(payload.get('errcode'), 1)
        self.assertIn('执行中', payload.get('errmsg') or '')

    def test_viewer_forbidden(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'viewer'
            sess['username'] = 'viewer'
            sess['group_ids'] = []
        resp = self.client.post('/cron_run_now?id=%s' % self.active_id)
        self.assertEqual(resp.status_code, 403)


class TestCronListRunNowButton(unittest.TestCase):
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
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.client = app.test_client()
        with app.app_context():
            from datas.model.cron_infos import CronInfos
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            db.create_all()
            cif = CronInfos(
                task_name='btn-task',
                task_keyword='说明',
                req_url='https://example.com/btn',
                status=1,
                created_at='t',
                updated_at='t',
            )
            db.session.add(cif)
            db.session.commit()

    def test_list_shows_run_now_for_admin(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'admin'
            sess['username'] = 'ops_admin'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('cp-page-dashboard', html)
        self.assertIn('cpRunNow(', html)
        self.assertIn("$.post('/cron_run_now'", html)
        self.assertIn('act-btn run', html)
        self.assertIn('health-badge', html)

    def test_vue_mount_point_data_attrs_present(self):
        """Redesign dashboard: inline JS posts id in request body (not Vue data-* props)."""
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'admin'
            sess['username'] = 'ops_admin'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('cp-dashboard-tbody', html)
        self.assertIn('function cpRunNow(cronId', html)
        self.assertIn("$.post('/cron_run_now', {id: cronId", html)
        self.assertIn('function cpToggleStatus(cronId', html)
        self.assertIn("$.post('/update_status', {id: cronId", html)
        self.assertIn('function cpRetire(cronId', html)
        self.assertIn("$.post('/cron_retire', {id: cronId", html)
        self.assertIn('tc-lifecycle active', html)

    def test_vue_mount_point_viewer_no_write_or_retire_url(self):
        """viewer 无 cron:write：无立即执行/编辑/下线操作按钮。"""
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'viewer'
            sess['username'] = 'viewer'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        tbody = html.split('</tbody>')[0].split('cp-dashboard-tbody')[1]
        self.assertNotIn('onclick="cpRunNow(', tbody)
        self.assertNotIn('onclick="cpRetire(', tbody)
        self.assertNotIn('act-btn run', tbody)
        self.assertNotIn('/cron_add', html)

    def test_run_url_already_contains_id_param(self):
        """Redesign AJAX 通过 POST body 传 id，脚本中不得拼接 ?id= 查询参数。"""
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'admin'
            sess['username'] = 'ops_admin'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn("$.post('/cron_run_now', {id: cronId", html)
        self.assertIn("$.post('/update_status', {id: cronId", html)
        self.assertNotIn('/cron_run_now?', html)
        self.assertNotIn('/update_status?', html)

    def test_viewer_no_run_now_button(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'viewer'
            sess['username'] = 'viewer'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertNotIn('act-btn run', html)
        self.assertNotIn('onclick="cpRunNow(', html)


if __name__ == '__main__':
    unittest.main()
