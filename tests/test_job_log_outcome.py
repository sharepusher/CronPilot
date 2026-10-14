# -*- coding:utf-8 -*-
import unittest

import requests

from app.services.job_log_outcome import (
    STATUS_ERROR,
    STATUS_FAIL,
    STATUS_SUCCESS,
    evaluate_http_response,
    exception_fail_reason,
    exception_failure_info,
    fatal_failure_info,
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

    def test_all_redirect_statuses_are_blocked(self):
        for code in (300, 301, 302, 303, 307, 308, 399):
            with self.subTest(code=code):
                status, reason = evaluate_http_response(code, '', None, '0')
                self.assertEqual(status, STATUS_FAIL)
                self.assertEqual(reason, 'redirect_blocked')

    def test_keyword_on_200(self):
        status, reason = evaluate_http_response(200, '{"error":true}', 'error', '1')
        self.assertEqual(status, STATUS_FAIL)
        self.assertEqual(reason, 'keyword')

    def test_success_200(self):
        status, reason = evaluate_http_response(200, '{"ok":true}', 'fail,error', '1')
        self.assertEqual(status, STATUS_SUCCESS)
        self.assertIsNone(reason)

    def test_pre_request_blocked(self):
        status, reason = pre_request_outcome('触发URL安全校验未通过: x')
        self.assertEqual(status, STATUS_ERROR)
        self.assertEqual(reason, 'blocked_url')

    def test_pre_request_blocked_legacy_wording(self):
        status, reason = pre_request_outcome('回调URL安全校验未通过: x')
        self.assertEqual(status, STATUS_ERROR)
        self.assertEqual(reason, 'blocked_url')

    def test_exception_timeout(self):
        self.assertEqual(exception_fail_reason(requests.exceptions.ReadTimeout()), 'timeout')

    def test_connect_timeout_is_distinct_from_read_timeout(self):
        connect = exception_failure_info(requests.exceptions.ConnectTimeout())
        read = exception_failure_info(requests.exceptions.ReadTimeout())
        self.assertEqual(connect['transport_state'], 'connect_failed')
        self.assertEqual(read['transport_state'], 'sent_no_response')

    def test_proxy_error_reports_connect_failure(self):
        info = exception_failure_info(requests.exceptions.ProxyError())
        self.assertEqual(info['transport_state'], 'connect_failed')

    def test_generic_connection_error_does_not_claim_connect_failed(self):
        info = exception_failure_info(requests.exceptions.ConnectionError())
        self.assertEqual(info['transport_state'], 'sent_no_response')

    def test_ssl_error_does_not_claim_connect_failed(self):
        info = exception_failure_info(requests.exceptions.SSLError())
        self.assertEqual(info['transport_state'], 'sent_no_response')

    def test_too_many_redirects_with_response_is_remote_response(self):
        response = requests.Response()
        response.status_code = 302
        info = exception_failure_info(
            requests.exceptions.TooManyRedirects('redirect limit', response=response)
        )
        self.assertEqual(
            info,
            {
                'failure_stage': 'remote_response',
                'fail_reason': 'redirect_limit',
                'transport_state': 'response_received',
            },
        )

    def test_too_many_redirects_without_response_is_not_connect_failure(self):
        info = exception_failure_info(requests.exceptions.TooManyRedirects('redirect limit'))
        self.assertEqual(info['transport_state'], 'sent_no_response')

    def test_outer_fatal_stage_depends_on_execution_boundary(self):
        exc = RuntimeError('unexpected')
        self.assertEqual(fatal_failure_info(exc)['failure_stage'], 'pre_request')
        self.assertEqual(fatal_failure_info(exc)['transport_state'], 'not_started')
        self.assertEqual(fatal_failure_info(exc, job_log_started=True)['failure_stage'], 'persistence')
        self.assertEqual(fatal_failure_info(exc, job_log_started=True)['transport_state'], 'prepared')
        self.assertEqual(fatal_failure_info(exc, request_call_started=True)['failure_stage'], 'transport')

    def test_client_incompatibility_is_not_connection_failure(self):
        exc = TypeError("HTTPConnection.__init__() got an unexpected keyword argument 'assert_hostname'")
        self.assertEqual(exception_fail_reason(exc), 'client_incompatible')
        self.assertEqual(
            exception_failure_info(exc),
            {
                'failure_stage': 'transport',
                'fail_reason': 'client_incompatible',
                'transport_state': 'client_failed',
            },
        )

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
