# -*- coding:utf-8 -*-
"""OPT-P2-13 job_health 写路径单测。"""
import os
import sys
import unittest

from flask import Flask

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import db
from app.services.job_health_service import (
    DEFAULT_FAILING_THRESHOLD,
    HEALTH_FAILING,
    HEALTH_OK,
    get_failing_threshold,
    update_job_health,
)
from app.services.job_log_outcome import STATUS_ERROR, STATUS_FAIL, STATUS_SUCCESS
from datas.model.job_health import JobHealth


class TestFailingThreshold(unittest.TestCase):
    def test_default_and_parse(self):
        self.assertEqual(get_failing_threshold({}), DEFAULT_FAILING_THRESHOLD)
        self.assertEqual(get_failing_threshold({'health_failing_threshold': '5'}), 5)
        self.assertEqual(get_failing_threshold({'health_failing_threshold': '0'}), 3)
        self.assertEqual(get_failing_threshold({'health_failing_threshold': 'x'}), 3)


class TestUpdateJobHealth(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app.config['TESTING'] = True
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_three_fails_marks_failing_when_n_is_3(self):
        cfg = {'health_failing_threshold': '3'}
        update_job_health(1, STATUS_FAIL, '2026-07-15 10:00:01', 'a', cron_config=cfg)
        row = db.session.get(JobHealth, 1)
        self.assertEqual(row.consecutive_failures, 1)
        self.assertEqual(row.health_status, HEALTH_OK)

        update_job_health(1, STATUS_FAIL, '2026-07-15 10:00:02', 'b', cron_config=cfg)
        update_job_health(1, STATUS_FAIL, '2026-07-15 10:00:03', 'c', cron_config=cfg)
        row = db.session.get(JobHealth, 1)
        self.assertEqual(row.consecutive_failures, 3)
        self.assertEqual(row.health_status, HEALTH_FAILING)

    def test_success_clears_streak(self):
        cfg = {'health_failing_threshold': '3'}
        update_job_health(2, STATUS_FAIL, '2026-07-15 10:00:01', 'a', cron_config=cfg)
        update_job_health(2, STATUS_FAIL, '2026-07-15 10:00:02', 'b', cron_config=cfg)
        update_job_health(2, STATUS_SUCCESS, '2026-07-15 10:00:03', 'c', cron_config=cfg)
        row = db.session.get(JobHealth, 2)
        self.assertEqual(row.consecutive_failures, 0)
        self.assertEqual(row.health_status, HEALTH_OK)
        self.assertEqual(row.last_run_status, STATUS_SUCCESS)

    def test_error_counts_as_failure(self):
        cfg = {'health_failing_threshold': '2'}
        update_job_health(3, STATUS_ERROR, '2026-07-15 10:00:01', 'a', cron_config=cfg)
        update_job_health(3, STATUS_ERROR, '2026-07-15 10:00:02', 'b', cron_config=cfg)
        row = db.session.get(JobHealth, 3)
        self.assertEqual(row.consecutive_failures, 2)
        self.assertEqual(row.health_status, HEALTH_FAILING)


class TestCronListHealthFilters(unittest.TestCase):
    """health=failing vs health=today_fail 口径分离。"""

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
        app.config['CRON_CONFIG'] = {
            'is_dev': '0',
            'block_private_ip': '0',
            'url_allow_hosts': '',
            'url_ssrf_observe_only': '1',
            'health_failing_threshold': '3',
        }
        db.init_app(app)
        from app.main import main as main_blueprint
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(main_blueprint)
        app.register_blueprint(rbac_blueprint)
        self.app = app
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
            from datas.model.job_health import JobHealth  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            db.create_all()
            self._seed()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _seed(self):
        from datas.model.cron_infos import CronInfos
        from datas.model.job_health import JobHealth
        from datas.model.job_log import JobLog
        from datas.model.rbac_user import RbacUser
        from datas.utils.times import get_now_time, get_today

        adm = RbacUser(username='adm_hf', role='admin', is_active=1, create_time=get_now_time())
        adm.set_password('pass')
        db.session.add(adm)

        now = get_now_time()
        today = get_today()
        t_ok = CronInfos(
            task_name='ok_today_clean',
            task_keyword='',
            req_url='https://example.com/ok',
            status=1,
            created_at=now,
            updated_at=now,
            scope_type='GLOBAL',
        )
        t_today = CronInfos(
            task_name='today_fail_only',
            task_keyword='',
            req_url='https://example.com/tf',
            status=1,
            created_at=now,
            updated_at=now,
            scope_type='GLOBAL',
        )
        t_streak = CronInfos(
            task_name='streak_failing',
            task_keyword='',
            req_url='https://example.com/sf',
            status=1,
            created_at=now,
            updated_at=now,
            scope_type='GLOBAL',
        )
        db.session.add_all([t_ok, t_today, t_streak])
        db.session.flush()

        db.session.add(
            JobLog(
                log_id='log-today-fail-1',
                cron_info_id=t_today.id,
                content='',
                status=STATUS_FAIL,
                create_time=today + ' 10:00:00',
            )
        )
        db.session.add(
            JobHealth(
                cron_info_id=t_today.id,
                last_run_at=today + ' 10:00:00',
                last_run_status=STATUS_FAIL,
                consecutive_failures=1,
                health_status=HEALTH_OK,
            )
        )
        db.session.add(
            JobHealth(
                cron_info_id=t_streak.id,
                last_run_at=today + ' 11:00:00',
                last_run_status=STATUS_FAIL,
                consecutive_failures=3,
                health_status=HEALTH_FAILING,
            )
        )
        db.session.commit()

    def _login_admin(self):
        resp = self.client.post(
            '/rbac/login',
            data={'username': 'adm_hf', 'password': 'pass', 'next': '/'},
        )
        self.assertEqual(resp.status_code, 302)

    def test_today_fail_lists_tasks_with_today_fail_runs(self):
        self._login_admin()
        html = self.client.get('/?health=today_fail').get_data(as_text=True)
        self.assertIn('today_fail_only', html)
        self.assertIn('today_fail_only', html)
        self.assertIn('cabin-name', html)
        self.assertNotIn('ok_today_clean', html)
        self.assertIn('health=today_fail', html)
        self.assertNotIn('opt-p2-13-metrics', html)
        # filter chips are now Vue-rendered; server HTML carries data-current-health instead
        self.assertIn('data-current-health="today_fail"', html)
        self.assertIn('运行与发布', html)
        self.assertIn('data-cron-id', html)

    def test_failing_filter_requires_health_status(self):
        self._login_admin()
        html = self.client.get('/?health=failing').get_data(as_text=True)
        self.assertIn('streak_failing', html)
        self.assertNotIn('today_fail_only', html)


if __name__ == '__main__':
    unittest.main()
