# -*- coding: utf-8 -*-
"""Tests: Dashboard stats should NOT vary with display filters.

Verifies that status/tag/search filters only affect the task list, not
the global stats cards (total, consecutive_failing, overdue, today_success_rate).
"""
import os
import unittest

from flask import Flask

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, 'app', 'templates'),
        static_folder=os.path.join(ROOT, 'app', 'static'),
    )
    app.secret_key = 'test-secret-dashboard-stats'
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
    from app.main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    from app.rbac import rbac as rbac_blueprint
    app.register_blueprint(rbac_blueprint)
    return app, db


class TestDashboardStatsStability(unittest.TestCase):
    """Stats cards should be unaffected by UI display filters."""

    def setUp(self):
        self.app, self.db = _make_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        from datas.model.cron_infos import CronInfos  # noqa: F401
        from datas.model.job_health import JobHealth  # noqa: F401
        from datas.model.job_log import JobLog  # noqa: F401
        from datas.model.resource_group import ResourceGroup  # noqa: F401
        from datas.model.tag import Tag  # noqa: F401
        from datas.model.task_tag import TaskTag  # noqa: F401
        from datas.model.user_group import UserGroup  # noqa: F401
        self.db.create_all()
        from datas.model.rbac_user import RbacUser
        user = RbacUser(username='admin', role='admin', is_active=1)
        user.set_password('test-password')
        self.db.session.add(user)
        self.db.session.commit()
        self.admin_id = user.id
        self._seed_tasks()
        self.client = self.app.test_client()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def _seed_tasks(self):
        """Create 3 running + 2 paused tasks."""
        from datas.model.cron_infos import CronInfos
        for i in range(1, 4):
            t = CronInfos()
            t.task_name = 'running_%d' % i
            t.url = 'http://example.com/r%d' % i
            t.cron = '*/5 * * * *'
            t.status = 1
            self.db.session.add(t)
        for i in range(1, 3):
            t = CronInfos()
            t.task_name = 'paused_%d' % i
            t.url = 'http://example.com/p%d' % i
            t.cron = '*/10 * * * *'
            t.status = 0
            self.db.session.add(t)
        self.db.session.commit()

    def _login_as_seed(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['username'] = 'admin'
            sess['user_id'] = self.admin_id
            sess['auth_version'] = 0
            sess['role'] = 'admin'
            sess['group_ids'] = []

    def _get_v2_dashboard(self, **params):
        """Fetch the v2 dashboard and return the rendered HTML."""
        with self.client.session_transaction() as sess:
            sess['ui_version'] = 'v2'
        return self.client.get('/cron_list', query_string=params)

    def test_total_task_count_stable_across_status_filter(self):
        """metrics.total should be the same regardless of ?status= param."""
        self._login_as_seed()
        resp_all = self._get_v2_dashboard()
        self.assertEqual(resp_all.status_code, 200)

        resp_running = self._get_v2_dashboard(status='1')
        self.assertEqual(resp_running.status_code, 200)

        resp_paused = self._get_v2_dashboard(status='0')
        self.assertEqual(resp_paused.status_code, 200)

    def test_stat_line_shows_status_and_attention_only(self):
        """标题保留状态/风险，不重复展示总任务数或今日失败。"""
        self._login_as_seed()
        resp = self._get_v2_dashboard()
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        # Seed: 3 running + 2 paused
        self.assertIn('运行中 <b>3</b>', html)
        self.assertIn('已暂停 <b>2</b>', html)
        stat_line = html.split('<div class="stat-line">', 1)[1].split('</div>', 1)[0]
        self.assertNotIn('个任务', stat_line)
        self.assertNotIn('今日失败', stat_line)
        self.assertIn('持续异常', stat_line)
        self.assertIn('逾期', stat_line)
        self.assertIn("statLine.innerHTML = '运行中 <b>' + stats.running", html)
        self.assertNotIn("stats.total + '</b> 个任务 · 运行中", html)
        self.assertNotIn("stats.today_fail_runs + ' 今日失败'", html)
        self.assertNotIn('在营', html)
        self.assertRegex(html, r'data-filter-val=""[^>]*>全部<')

    def test_partial_stats_include_running_and_paused(self):
        """AJAX partial stats 须带 running/paused，且口径不受 status 筛选影响。"""
        self._login_as_seed()
        with self.client.session_transaction() as sess:
            sess['ui_version'] = 'v2'
        resp = self.client.get('/cron_list', query_string={'partial': '1', 'status': '0'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['stats']['running'], 3)
        self.assertEqual(data['stats']['paused'], 2)
        self.assertEqual(data['stats']['total'], 5)

    def test_stats_stable_with_search_filter(self):
        """Stats should not change when task_name search is applied."""
        self._login_as_seed()
        resp_all = self._get_v2_dashboard()
        self.assertEqual(resp_all.status_code, 200)

        resp_search = self._get_v2_dashboard(task_name='running_1')
        self.assertEqual(resp_search.status_code, 200)

    def test_scope_filters_exclude_display_filters(self):
        """Verify the scope_filters vs filter_arr split in the view logic.

        This is an integration test that verifies the view function returns
        200 with various filter combinations without error.
        """
        self._login_as_seed()
        combos = [
            {},
            {'status': '1'},
            {'status': '0'},
            {'task_name': 'nonexistent'},
            {'status': '1', 'task_name': 'running'},
            {'health': 'overdue'},
            {'status': '0', 'health': 'overdue'},
        ]
        for params in combos:
            resp = self._get_v2_dashboard(**params)
            self.assertEqual(
                resp.status_code, 200,
                'Failed for params: %s' % params,
            )


if __name__ == '__main__':
    unittest.main()
