# -*- coding: utf-8 -*-
"""执行记录详情页端到端渲染测试。

验证 View → Repository → Template 完整链路，
防止跨模块重命名（如 log_id → trace_id）导致运行时 AttributeError。
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask


def _make_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, 'app', 'templates'),
        static_folder=os.path.join(ROOT, 'app', 'static'),
    )
    app.secret_key = 'test-secret-key-logdetail'
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
    from app.services.job_log_display import (
        job_log_badge, job_log_content_preview,
        job_log_status_line, job_log_status_badge_class,
    )
    from app.services.cron_schedule_display import (
        format_cron_expression, format_duration, humanize_schedule,
    )
    app.jinja_env.filters['job_log_status_line'] = job_log_status_line
    app.jinja_env.filters['job_log_content_preview'] = job_log_content_preview
    app.jinja_env.filters['job_log_badge'] = job_log_badge
    app.jinja_env.filters['job_log_status_badge_class'] = job_log_status_badge_class
    app.jinja_env.filters['humanize_schedule'] = humanize_schedule
    app.jinja_env.filters['format_cron_expression'] = format_cron_expression
    app.jinja_env.filters['format_duration'] = format_duration
    from app.main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    from app.rbac import rbac as rbac_blueprint
    app.register_blueprint(rbac_blueprint)
    return app, db


def _seed_user_and_log(db):
    """Seed admin user + one task + one job_log row."""
    from datas.model.rbac_user import RbacUser
    from datas.model.cron_infos import CronInfos
    from datas.model.job_log import JobLog
    from datas.model.job_log_items import JobLogItems
    from datas.model.job_health import JobHealth
    from datas.model.resource_group import ResourceGroup
    from datas.model.tag import Tag
    from datas.utils.times import utc_now_hms
    from app.auth.password import hash_password
    import uuid

    u = RbacUser(
        username='admin', password_hash=hash_password('changeme'),
        role='admin', is_active=1, status_reason='seed',
        must_reset_password=0, email='', job_title='', nickname='',
        api_token='', api_token_expires_at=0, last_login_at=0,
        create_time=utc_now_hms(),
    )
    db.session.add(u)
    db.session.flush()

    cif = CronInfos(
        task_name='test-task', req_url='https://example.com/test',
        minute='*/5', status=1, scope_type='GLOBAL',
        last_operator_name=u.username, req_method='GET', req_body='',
        timeout_sec=5,
        created_at=utc_now_hms(), updated_at=utc_now_hms(),
    )
    db.session.add(cif)
    db.session.flush()

    trace_uuid = str(uuid.uuid4())
    jl = JobLog(
        trace_id=trace_uuid, cron_info_id=cif.id,
        content='HTTP 200 OK', http_status=200,
        status='success', fail_reason='',
        create_time=utc_now_hms(), take_time=0,
        started_at=utc_now_hms(), finished_at=utc_now_hms(),
    )
    db.session.add(jl)
    db.session.flush()

    jli = JobLogItems(trace_id=trace_uuid, content='step 1: done')
    db.session.add(jli)

    db.session.commit()
    return u, cif, jl, trace_uuid


class TestJobLogDetailIntegration(unittest.TestCase):
    """验证 job_log_detail 路由端到端渲染链路。"""

    def setUp(self):
        self.app, self.db = _make_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.create_all()
        self.user, self.cif, self.jl, self.trace_uuid = _seed_user_and_log(self.db)

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def _login(self, client):
        client.post('/rbac/login', data={
            'username': 'admin', 'password': 'changeme',
        })

    def test_v1_detail_renders_without_error(self):
        """v1 详情页渲染无 500。"""
        with self.app.test_client() as c:
            c.set_cookie('cp_ui_mode', 'classic')
            self._login(c)
            r = c.get(f'/job_log_detail?id={self.jl.id}')
            self.assertEqual(r.status_code, 200)
            html = r.data.decode()
            self.assertIn('追踪码', html)
            self.assertIn(self.trace_uuid, html)
            self.assertNotIn('Internal Server Error', html)

    def test_v2_detail_renders_without_error(self):
        """v2 (redesign) 详情页渲染无 500。"""
        with self.app.test_client() as c:
            c.set_cookie('cp_ui_mode', 'console')
            self._login(c)
            r = c.get(f'/job_log_detail?id={self.jl.id}')
            self.assertEqual(r.status_code, 200)
            html = r.data.decode()
            self.assertNotIn('Internal Server Error', html)
            self.assertIn('追踪码', html)
            self.assertIn(str(self.jl.id), html)

    def test_v1_detail_not_found(self):
        """v1 不存在的记录不报 500。"""
        with self.app.test_client() as c:
            c.set_cookie('cp_ui_mode', 'classic')
            self._login(c)
            r = c.get('/job_log_detail?id=99999')
            self.assertEqual(r.status_code, 200)
            self.assertNotIn('Internal Server Error', r.data.decode())

    def test_v2_detail_not_found(self):
        """v2 不存在的记录不报 500。"""
        with self.app.test_client() as c:
            c.set_cookie('cp_ui_mode', 'console')
            self._login(c)
            r = c.get('/job_log_detail?id=99999')
            self.assertEqual(r.status_code, 200)
            html = r.data.decode()
            self.assertNotIn('Internal Server Error', html)
            self.assertIn('记录不存在', html)

    def test_job_log_item_list_by_trace_id(self):
        """通过 trace_id 查询进度列表不报 500。"""
        with self.app.test_client() as c:
            c.set_cookie('cp_ui_mode', 'classic')
            self._login(c)
            r = c.get(f'/job_log_item_list?trace_id={self.trace_uuid}')
            self.assertIn(r.status_code, [200, 302])
            if r.status_code == 200:
                self.assertNotIn('Internal Server Error', r.data.decode())

    def test_repo_method_names_consistent(self):
        """Repo 方法名与 views.py 调用一致。"""
        from app.repositories.job_log_repository import JobLogRepository
        repo = JobLogRepository(self.db.session)
        self.assertTrue(hasattr(repo, 'get_by_trace_id'),
                        'JobLogRepository must have get_by_trace_id')
        self.assertTrue(hasattr(repo, 'items_for_trace_id'),
                        'JobLogRepository must have items_for_trace_id')
        self.assertFalse(hasattr(repo, 'get_by_log_id'),
                         'Old method get_by_log_id should not exist')
        self.assertFalse(hasattr(repo, 'items_for_log_id'),
                         'Old method items_for_log_id should not exist')


if __name__ == '__main__':
    unittest.main()
