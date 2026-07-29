# -*- coding: utf-8 -*-
"""B1 执行状态机单元测试（OPT-P1-01 Phase B1）。

覆盖：
  - job_log_outcome: 状态常量 / evaluate_http_response / is_timeout_exception / should_alert
  - job_log_display: job_log_badge / job_log_status_badge_class 全状态映射
  - JobLog 模型列存在性
"""
import unittest

from app.services.job_log_outcome import (
    STATUS_ERROR,
    STATUS_FAIL,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    evaluate_http_response,
    exception_fail_reason,
    is_timeout_exception,
    should_alert,
)
from app.services.job_log_display import (
    job_log_badge,
    job_log_status_badge_class,
)


class TestStatusConstants(unittest.TestCase):
    def test_constants_distinct(self):
        vals = [STATUS_SUCCESS, STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT, STATUS_PENDING, STATUS_RUNNING]
        self.assertEqual(len(vals), len(set(vals)))

    def test_constants_are_strings(self):
        for s in [STATUS_SUCCESS, STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT, STATUS_PENDING, STATUS_RUNNING]:
            self.assertIsInstance(s, str)


class TestEvaluateHttpResponse(unittest.TestCase):
    def test_2xx_no_keywords(self):
        status, reason = evaluate_http_response(200, '{"ok":1}', None, None)
        self.assertEqual(status, STATUS_SUCCESS)
        self.assertIsNone(reason)

    def test_5xx_fail(self):
        status, reason = evaluate_http_response(500, 'err', None, None)
        self.assertEqual(status, STATUS_FAIL)
        self.assertEqual(reason, 'http_5xx')

    def test_4xx_fail_when_flag_enabled(self):
        status, reason = evaluate_http_response(404, 'not found', None, '1')
        self.assertEqual(status, STATUS_FAIL)
        self.assertEqual(reason, 'http_4xx')

    def test_4xx_success_when_flag_disabled(self):
        status, reason = evaluate_http_response(404, 'not found', None, '0')
        self.assertEqual(status, STATUS_SUCCESS)

    def test_keyword_match_gives_fail(self):
        status, reason = evaluate_http_response(200, 'result: error occurred', 'error', None)
        self.assertEqual(status, STATUS_FAIL)
        self.assertEqual(reason, 'keyword')

    def test_keyword_no_match(self):
        status, reason = evaluate_http_response(200, 'all good', 'error', None)
        self.assertEqual(status, STATUS_SUCCESS)

    def test_multiple_keywords_one_match(self):
        status, reason = evaluate_http_response(200, 'timeout reached', 'error,timeout', None)
        self.assertEqual(status, STATUS_FAIL)


class TestIsTimeoutException(unittest.TestCase):
    def test_requests_timeout(self):
        import requests as req
        self.assertTrue(is_timeout_exception(req.exceptions.Timeout()))
        self.assertTrue(is_timeout_exception(req.exceptions.ConnectTimeout()))
        self.assertTrue(is_timeout_exception(req.exceptions.ReadTimeout()))

    def test_non_timeout_exception(self):
        self.assertFalse(is_timeout_exception(ValueError("oops")))
        import requests as req
        self.assertFalse(is_timeout_exception(req.exceptions.ConnectionError()))

    def test_exception_fail_reason_timeout(self):
        import requests as req
        self.assertEqual(exception_fail_reason(req.exceptions.ReadTimeout()), 'timeout')

    def test_exception_fail_reason_connection(self):
        import requests as req
        self.assertEqual(exception_fail_reason(req.exceptions.ConnectionError()), 'connection')

    def test_exception_fail_reason_internal(self):
        self.assertEqual(exception_fail_reason(RuntimeError("boom")), 'internal')


class TestShouldAlert(unittest.TestCase):
    def test_fail_alerts(self):
        self.assertTrue(should_alert(STATUS_FAIL))

    def test_error_alerts(self):
        self.assertTrue(should_alert(STATUS_ERROR))

    def test_success_no_alert(self):
        self.assertFalse(should_alert(STATUS_SUCCESS))

    def test_timeout_alerts(self):
        self.assertTrue(should_alert(STATUS_TIMEOUT))

    def test_running_no_alert(self):
        self.assertFalse(should_alert(STATUS_RUNNING))

    def test_pending_no_alert(self):
        self.assertFalse(should_alert(STATUS_PENDING))


class TestJobLogBadge(unittest.TestCase):
    def test_success(self):
        text, tone = job_log_badge(STATUS_SUCCESS)
        self.assertIsNotNone(text)
        self.assertEqual(tone, 'ok')

    def test_fail(self):
        text, tone = job_log_badge(STATUS_FAIL)
        self.assertIsNotNone(text)
        self.assertEqual(tone, 'fail')

    def test_error(self):
        text, tone = job_log_badge(STATUS_ERROR)
        self.assertIsNotNone(text)
        self.assertEqual(tone, 'error')

    def test_timeout(self):
        text, tone = job_log_badge(STATUS_TIMEOUT)
        self.assertIsNotNone(text)
        self.assertEqual(tone, 'timeout')

    def test_running(self):
        text, tone = job_log_badge(STATUS_RUNNING)
        self.assertIsNotNone(text)
        self.assertEqual(tone, 'running')

    def test_pending(self):
        text, tone = job_log_badge(STATUS_PENDING)
        self.assertIsNotNone(text)
        self.assertEqual(tone, 'pending')

    def test_unknown_returns_none(self):
        text, tone = job_log_badge(None)
        self.assertIsNone(text)
        self.assertIsNone(tone)

    def test_all_statuses_have_text(self):
        for s in [STATUS_SUCCESS, STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT, STATUS_RUNNING, STATUS_PENDING]:
            text, tone = job_log_badge(s)
            self.assertIsNotNone(text, msg='badge text None for status=%s' % s)
            self.assertIsNotNone(tone, msg='badge tone None for status=%s' % s)


class TestJobLogStatusBadgeClass(unittest.TestCase):
    def test_success_label(self):
        self.assertEqual(job_log_status_badge_class(STATUS_SUCCESS), 'label-success')

    def test_fail_label(self):
        self.assertEqual(job_log_status_badge_class(STATUS_FAIL), 'label-danger')

    def test_error_label(self):
        self.assertEqual(job_log_status_badge_class(STATUS_ERROR), 'label-warning')

    def test_timeout_label(self):
        self.assertEqual(job_log_status_badge_class(STATUS_TIMEOUT), 'label-timeout')

    def test_running_label(self):
        self.assertEqual(job_log_status_badge_class(STATUS_RUNNING), 'label-running')

    def test_pending_label(self):
        self.assertEqual(job_log_status_badge_class(STATUS_PENDING), 'label-pending')

    def test_none_fallback(self):
        self.assertEqual(job_log_status_badge_class(None), 'label-default')

    def test_unknown_fallback(self):
        self.assertEqual(job_log_status_badge_class('bogus'), 'label-default')

    def test_all_statuses_return_nonempty_class(self):
        for s in [STATUS_SUCCESS, STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT, STATUS_RUNNING, STATUS_PENDING]:
            cls = job_log_status_badge_class(s)
            self.assertTrue(cls.startswith('label-'), msg='bad class for status=%s: %s' % (s, cls))


class TestJobLogModelColumns(unittest.TestCase):
    """确认 JobLog 模型已定义 B1 新列。"""

    def test_b1_columns_exist(self):
        from datas.model.job_log import JobLog
        cols = {c.key for c in JobLog.__mapper__.column_attrs}
        for col in ('status', 'fail_reason', 'started_at', 'finished_at', 'timeout_sec'):
            self.assertIn(col, cols, msg='JobLog missing column: %s' % col)


if __name__ == '__main__':
    unittest.main()
