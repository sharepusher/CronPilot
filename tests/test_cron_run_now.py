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
        self.assertIn('data-can-write="true"', html)
        self.assertIn('/cron_run_now?', html)
        self.assertIn('health-dot', html)
        self.assertIn('jumbotron', html)

    def test_vue_mount_point_data_attrs_present(self):
        """Vue 挂载点 data-* 属性由服务端渲染，URL props 按权限条件出现。状态徽章由 Jinja 渲染。"""
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'admin'
            sess['username'] = 'ops_admin'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        # 挂载点 id 前缀
        self.assertIn('id="cron-ops-', html)
        # 核心 props（所有角色均有）
        self.assertIn('data-cron-id=', html)
        self.assertIn('data-status=', html)
        self.assertIn('data-can-write=', html)
        self.assertIn('data-can-retire=', html)
        self.assertIn('data-has-url=', html)
        self.assertIn('data-log-url=', html)
        # admin 有 cron:write → write URL props 存在
        self.assertIn('data-update-url=', html)
        self.assertIn('data-run-url=', html)
        self.assertIn('data-edit-url=', html)
        # admin 有 cron:retire → retire URL 存在
        self.assertIn('data-retire-url=', html)
        # Vue bundle 已引入
        self.assertIn('dist/cron-status-cell.js', html)
        # 状态徽章由 Jinja 渲染（id="status-badge-N"）
        self.assertIn('id="status-badge-', html)

    def test_vue_mount_point_viewer_no_write_or_retire_url(self):
        """viewer 角色无 cron:write / cron:retire，write/retire URL props 不出现在 HTML。"""
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'viewer'
            sess['username'] = 'viewer'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('data-can-write="false"', html)
        self.assertIn('data-can-retire="false"', html)
        self.assertNotIn('data-update-url=', html)
        self.assertNotIn('data-run-url=', html)
        self.assertNotIn('data-edit-url=', html)
        self.assertNotIn('data-retire-url=', html)
        self.assertNotIn('/update_status?', html)
        self.assertNotIn('/cron_retire?', html)

    def test_run_url_already_contains_id_param(self):
        """data-run-url / data-update-url 由 url_for 生成时已含 ?id=N。
        Vue 组件必须直接使用该 URL，不得再追加 ?id=。
        本测试拦截"URL 双拼"bug（props.runUrl + '?id=' + cronId → id=1?id=1）。"""
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'admin'
            sess['username'] = 'ops_admin'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        import re
        # data-run-url 值须包含 ?id= 且值中不能再出现第二个 ?
        run_urls = re.findall(r'data-run-url="([^"]+)"', html)
        self.assertTrue(run_urls, 'data-run-url 属性未找到')
        for url in run_urls:
            self.assertIn('?id=', url, 'data-run-url 应已含 ?id= 参数')
            # URL 里不应出现两个 ?（双拼特征）
            self.assertEqual(url.count('?'), 1, f'data-run-url 含多个 ?，疑似双拼: {url}')
        # data-update-url 同样检查
        update_urls = re.findall(r'data-update-url="([^"]+)"', html)
        self.assertTrue(update_urls, 'data-update-url 属性未找到')
        for url in update_urls:
            self.assertIn('?id=', url)
            self.assertEqual(url.count('?'), 1, f'data-update-url 含多个 ?，疑似双拼: {url}')

    def test_viewer_no_run_now_button(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'viewer'
            sess['username'] = 'viewer'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('data-can-write="false"', html)
        self.assertNotIn('data-can-write="true"', html)


if __name__ == '__main__':
    unittest.main()
