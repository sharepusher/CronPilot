# -*- coding:utf-8 -*-
import unittest

import requests

from app.services.job_log_outcome import (
    STATUS_ERROR,
    STATUS_FAIL,
    STATUS_SUCCESS,
    evaluate_http_response,
    exception_fail_reason,
    fail_on_http_4xx_5xx_enabled,
    keyword_matched,
    pre_request_outcome,
    should_alert,
)


class TestJobLogOutcome(unittest.TestCase):
    def test_http_502_default_fail(self):
        status, reason = evaluate_http_response(502, '', 'fail', '1')
        self.assertEqual(status, STATUS_FAIL)
        self.assertEqual(reason, 'http_5xx')

    def test_http_502_disabled(self):
        status, reason = evaluate_http_response(502, '', 'fail', '0')
        self.assertEqual(status, STATUS_SUCCESS)
        self.assertIsNone(reason)

    def test_keyword_on_200(self):
        status, reason = evaluate_http_response(200, '{"error":true}', 'error', '1')
        self.assertEqual(status, STATUS_FAIL)
        self.assertEqual(reason, 'keyword')

    def test_success_200(self):
        status, reason = evaluate_http_response(200, '{"ok":true}', 'fail,error', '1')
        self.assertEqual(status, STATUS_SUCCESS)
        self.assertIsNone(reason)

    def test_pre_request_blocked(self):
        status, reason = pre_request_outcome('回调URL安全校验未通过: x')
        self.assertEqual(status, STATUS_ERROR)
        self.assertEqual(reason, 'blocked_url')

    def test_exception_timeout(self):
        self.assertEqual(exception_fail_reason(requests.exceptions.ReadTimeout()), 'timeout')

    def test_should_alert(self):
        self.assertTrue(should_alert(STATUS_FAIL))
        self.assertFalse(should_alert(STATUS_SUCCESS))

    def test_fail_on_flag(self):
        self.assertTrue(fail_on_http_4xx_5xx_enabled(None))
        self.assertFalse(fail_on_http_4xx_5xx_enabled('0'))

    def test_keyword_matched_case_insensitive(self):
        self.assertTrue(keyword_matched('FAIL hard', 'fail'))


if __name__ == '__main__':
    unittest.main()
