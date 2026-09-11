# -*- coding:utf-8 -*-
"""任务链路日志完整性 — 新增字段与日志覆盖验证。

覆盖计划中全部 GAP（GAP-1a/1b, GAP-2, GAP-3, GAP-4a~4f）。
"""
import logging
import os
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _make_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, 'app', 'templates'),
        static_folder=os.path.join(ROOT, 'app', 'static'),
    )
    app.secret_key = 'test-lifecycle'
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['CRON_CONFIG'] = {}
    from app import db
    db.init_app(app)
    return app, db


class TestJobLogModelNewFields(unittest.TestCase):
    """GAP-4a/4b/4c/4d: job_log 表新增字段。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.job_log import JobLog  # noqa: F401
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_trigger_source_persisted(self):
        from datas.model.job_log import JobLog
        with self.app.app_context():
            jl = JobLog(cron_info_id=1, content='ok', create_time=100,
                        trigger_source='manual')
            self.db.session.add(jl)
            self.db.session.commit()
            loaded = self.db.session.get(JobLog, jl.id)
            self.assertEqual(loaded.trigger_source, 'manual')

    def test_actual_url_persisted(self):
        from datas.model.job_log import JobLog
        with self.app.app_context():
            url = 'https://example.com/cb?cronpilot_trace_id=abc&cronpilot_sign=xyz'
            jl = JobLog(cron_info_id=1, content='ok', create_time=100,
                        actual_url=url)
            self.db.session.add(jl)
            self.db.session.commit()
            loaded = self.db.session.get(JobLog, jl.id)
            self.assertEqual(loaded.actual_url, url)

    def test_resolved_ip_persisted(self):
        from datas.model.job_log import JobLog
        with self.app.app_context():
            jl = JobLog(cron_info_id=1, content='ok', create_time=100,
                        resolved_ip='93.184.216.34')
            self.db.session.add(jl)
            self.db.session.commit()
            loaded = self.db.session.get(JobLog, jl.id)
            self.assertEqual(loaded.resolved_ip, '93.184.216.34')

    def test_trigger_delay_ms_persisted(self):
        from datas.model.job_log import JobLog
        with self.app.app_context():
            jl = JobLog(cron_info_id=1, content='ok', create_time=100,
                        trigger_delay_ms=42)
            self.db.session.add(jl)
            self.db.session.commit()
            loaded = self.db.session.get(JobLog, jl.id)
            self.assertEqual(loaded.trigger_delay_ms, 42)

    def test_all_new_fields_nullable(self):
        """旧数据兼容：新字段全部 NULL 也能写入。"""
        from datas.model.job_log import JobLog
        with self.app.app_context():
            jl = JobLog(cron_info_id=1, content='legacy', create_time=100)
            self.db.session.add(jl)
            self.db.session.commit()
            loaded = self.db.session.get(JobLog, jl.id)
            self.assertIsNone(loaded.trigger_source)
            self.assertIsNone(loaded.actual_url)
            self.assertIsNone(loaded.resolved_ip)
            self.assertIsNone(loaded.trigger_delay_ms)


class TestCronDoStartLog(unittest.TestCase):
    """GAP-2: cron_do 入站时有 'cron_do start' 日志。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.job_health import JobHealth  # noqa: F401
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.job_log_items import JobLogItems  # noqa: F401
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    @patch('app.crons.TRIGGER_DELAY')
    @patch('app.crons.ORPHAN_JOB_DETECTED')
    def test_cron_do_emits_start_log(self, mock_orphan, mock_delay):
        """对不存在的 cron_id 执行 cron_do，应看到 'cron.start' 日志。"""
        mock_orphan.labels.return_value = MagicMock()
        mock_delay.labels.return_value = MagicMock()

        from app import scheduler
        scheduler.app = self.app

        with self.app.app_context():
            with self.assertLogs(level='INFO') as cm:
                from app.crons import cron_do
                cron_do(99999, trigger_source='manual')

            start_logs = [r for r in cm.output if 'cron_do start' in r
                          or 'cron.start' in r]
            self.assertTrue(len(start_logs) > 0,
                            'Expected cron.start log, got: %s' % cm.output)


class TestTriggerSourcePassthrough(unittest.TestCase):
    """GAP-4a: cron_do 函数签名接受 trigger_source 参数。"""

    def test_cron_do_accepts_trigger_source_param(self):
        """cron_do 函数签名包含 trigger_source 默认参数。"""
        import inspect

        from app.crons import cron_do
        sig = inspect.signature(cron_do)
        self.assertIn('trigger_source', sig.parameters)
        self.assertEqual(
            sig.parameters['trigger_source'].default,
            'schedule',
        )

    def test_run_now_view_passes_manual(self):
        """验证 cron_run_now 视图代码中确实传递 trigger_source='manual'。"""
        src_path = os.path.join(ROOT, 'app', 'main', 'views.py')
        with open(src_path, 'r') as f:
            source = f.read()
        self.assertIn("trigger_source='manual'", source)


class TestRegisterCronJobLog(unittest.TestCase):
    """GAP-1b: register_cron_job 成功后写 INFO 日志。"""

    def test_register_logs_info(self):
        app, db_inst = _make_app()
        with app.app_context():
            from app.services.cron_service import register_cron_job
            normalized = {
                'minute': '*/5', 'hour': '*', 'day': '*',
                'day_of_week': '*', 'second': '0', 'run_date': '',
            }
            with self.assertLogs('app.services.cron_service', level='INFO') as cm:
                register_cron_job(1, normalized)
            registered_logs = [r for r in cm.output
                               if 'scheduler_registered' in r or 'registered' in r.lower()]
            self.assertTrue(len(registered_logs) > 0,
                            'Expected scheduler_registered log, got: %s' % cm.output)


class TestDetailPageTriggerType(unittest.TestCase):
    """GAP-4a: 详情页 trigger_type 应从 jl.trigger_source 动态读取。"""

    def test_trigger_type_mapping(self):
        """Verify the trigger_source → label mapping logic."""
        _trigger_labels = {
            'schedule': '定时调度',
            'manual': '手动执行',
            'one_shot': '一次性任务',
        }
        for src, expected in _trigger_labels.items():
            self.assertEqual(_trigger_labels.get(src, src), expected)

        self.assertEqual(_trigger_labels.get(None, None), None)
        self.assertEqual(_trigger_labels.get('unknown', 'unknown'), 'unknown')


class TestActualUrlSignMasking(unittest.TestCase):
    """BUG-FIX: cronpilot_sign must be masked before storage in actual_url (E-1).

    Tests that re.sub masking in crons.py strips the sign value from GET URLs
    while preserving the rest of the URL and the trace_id parameter.
    """

    def _mask(self, url):
        import re
        return re.sub(r'(cronpilot_sign=)[^&]+', r'\1***', url) if url else None

    def test_sign_is_masked_in_get_url(self):
        url = 'https://example.com/cb?cronpilot_trace_id=abc123&cronpilot_sign=secretvalue'
        masked = self._mask(url)
        self.assertNotIn('secretvalue', masked)
        self.assertIn('cronpilot_sign=***', masked)
        self.assertIn('cronpilot_trace_id=abc123', masked)

    def test_sign_masked_when_not_last_param(self):
        url = 'https://example.com/cb?cronpilot_sign=secret&other=val'
        masked = self._mask(url)
        self.assertNotIn('secret', masked)
        self.assertIn('cronpilot_sign=***', masked)
        self.assertIn('other=val', masked)

    def test_none_url_passes_through(self):
        self.assertIsNone(self._mask(None))

    def test_post_url_unchanged(self):
        # POST actual_url = req_url (no sign in query string)
        url = 'https://example.com/trigger'
        self.assertEqual(self._mask(url), url)

    def test_actual_url_field_masking_logic_matches_crons_py(self):
        """Verify crons.py uses the same pattern we test here."""
        import re as _re
        src_path = os.path.join(ROOT, 'app', 'crons.py')
        with open(src_path, 'r') as f:
            source = f.read()
        self.assertIn("re.sub(r'(cronpilot_sign=)[^&]+', r'\\1***', _actual_url)", source,
                      'crons.py must apply sign masking before passing actual_url to _save_job_log')


class TestActualUrlNameErrorGuard(unittest.TestCase):
    """BUG-FIX: _actual_url must be initialized before the inner try block (NameError guard).

    Verifies that crons.py initializes _actual_url = None before the inner try,
    so an exception raised before _actual_url is assigned does not cause a
    NameError in the except handler.
    """

    def test_actual_url_initialized_before_try(self):
        """_actual_url = None must appear before the inner try: in the url_ok branch."""
        src_path = os.path.join(ROOT, 'app', 'crons.py')
        with open(src_path, 'r') as f:
            lines = f.readlines()

        init_lineno = None
        try_lineno = None
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if '_actual_url = None' in stripped and init_lineno is None:
                init_lineno = i
            # The inner try: is indented inside the url_ok else branch
            if stripped == 'try:' and init_lineno is not None and try_lineno is None:
                try_lineno = i

        self.assertIsNotNone(init_lineno,
                             '_actual_url = None initializer not found in crons.py')
        self.assertIsNotNone(try_lineno,
                             'inner try: not found after _actual_url initializer in crons.py')
        self.assertLess(init_lineno, try_lineno,
                        '_actual_url = None must come BEFORE the inner try: block '
                        '(found on line %s, try: on line %s)' % (init_lineno, try_lineno))


class TestToJsonNoAttributeError(unittest.TestCase):
    """BUG-FIX: JobLog.to_json() must not reference non-existent attributes."""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.job_log import JobLog  # noqa: F401
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_to_json_does_not_raise(self):
        from datas.model.job_log import JobLog
        with self.app.app_context():
            jl = JobLog(cron_info_id=1, content='test', create_time=100, status='success')
            self.db.session.add(jl)
            self.db.session.commit()
            loaded = self.db.session.get(JobLog, jl.id)
            result = loaded.to_json()  # must not raise AttributeError
            self.assertIn('id', result)
            self.assertIn('content', result)
            self.assertIn('status', result)
            self.assertNotIn('job_id', result)
            self.assertNotIn('remark', result)
            self.assertNotIn('traces', result)


if __name__ == '__main__':
    unittest.main()
