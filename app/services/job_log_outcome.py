# -*- coding:utf-8 -*-
"""job_log 执行成败判定（OPT-P1-01/02）。"""

import requests

STATUS_SUCCESS = 'success'
STATUS_FAIL = 'fail'
STATUS_ERROR = 'error'
STATUS_TIMEOUT = 'timeout'
STATUS_PENDING = 'pending'
STATUS_RUNNING = 'running'

# 术语统一前写入的历史 job_log 仍存着旧文案，识别须同时兼容两种前缀
BLOCKED_URL_PREFIXES = ('触发URL安全校验未通过', '回调URL安全校验未通过')


def fail_on_http_4xx_5xx_enabled(flag):
    if flag is None:
        return True
    return str(flag).strip().lower() in ('1', 'true', 'yes', 'on')


def _parse_keywords(error_keyword):
    if not error_keyword:
        return []
    return [k.strip().lower() for k in str(error_keyword).replace('，', ',').split(',') if k.strip()]


def keyword_matched(body, error_keyword):
    keywords = _parse_keywords(error_keyword)
    if not keywords:
        return False
    text = (body or '').lower()
    return any(kw in text for kw in keywords)


def evaluate_http_response(http_status, body, error_keyword, fail_on_http_flag):
    """HTTP 已返回时综合判定 status / fail_reason。"""
    code = int(http_status)
    # cron_do explicitly does not follow redirects.  A 3xx therefore proves
    # only that the first hop replied, never that the configured trigger URL's
    # destination was invoked.  This policy is independent of the optional
    # 4xx/5xx compatibility switch.
    if 300 <= code < 400:
        return STATUS_FAIL, 'redirect_blocked'
    if fail_on_http_4xx_5xx_enabled(fail_on_http_flag):
        if code >= 500:
            return STATUS_FAIL, 'http_5xx'
        if code >= 400:
            return STATUS_FAIL, 'http_4xx'
    if keyword_matched(body, error_keyword):
        return STATUS_FAIL, 'keyword'
    return STATUS_SUCCESS, None


def exception_fail_reason(exc):
    """Return the stable failure reason for a transport or execution error."""
    return exception_failure_info(exc)['fail_reason']


def exception_failure_info(exc):
    """Classify transport failures and retain whether a response was possible."""
    if isinstance(exc, requests.exceptions.TooManyRedirects):
        # Requests retains the last response when redirect resolution exceeds
        # its limit.  That proves a remote HTTP response was received; it is
        # not a connection-establishment failure.
        if getattr(exc, 'response', None) is not None:
            return {
                'failure_stage': 'remote_response',
                'fail_reason': 'redirect_limit',
                'transport_state': 'response_received',
            }
        # A hand-built or non-standard exception may not retain a response.
        # The request call was entered, but we must not claim it never
        # connected.
        return {
            'failure_stage': 'transport',
            'fail_reason': 'redirect_limit',
            'transport_state': 'sent_no_response',
        }
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return {
            'failure_stage': 'transport',
            'fail_reason': 'timeout',
            'transport_state': 'sent_no_response',
        }
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return {
            'failure_stage': 'transport',
            'fail_reason': 'timeout',
            'transport_state': 'connect_failed',
        }
    if isinstance(exc, requests.exceptions.Timeout):
        return {
            'failure_stage': 'transport',
            'fail_reason': 'timeout',
            'transport_state': 'sent_no_response',
        }
    if isinstance(exc, requests.exceptions.ProxyError):
        return {
            'failure_stage': 'transport',
            'fail_reason': 'connection',
            'transport_state': 'connect_failed',
        }
    if isinstance(exc, requests.exceptions.ConnectionError):
        # ConnectionError is also the wrapper for remote disconnects and TLS
        # failures.  Without a more specific connect/proxy subtype, the only
        # sound assertion is that the call was attempted.
        return {
            'failure_stage': 'transport',
            'fail_reason': 'connection',
            'transport_state': 'sent_no_response',
        }
    if isinstance(exc, TypeError) and 'assert_hostname' in str(exc):
        return {
            'failure_stage': 'transport',
            'fail_reason': 'client_incompatible',
            'transport_state': 'client_failed',
        }
    return {
        'failure_stage': 'transport',
        'fail_reason': 'internal',
        'transport_state': 'unknown_failure',
    }


def fatal_failure_info(exc, request_call_started=False, job_log_started=False):
    """Classify an outer cron fatal without defaulting every error to pre-request."""
    if request_call_started:
        return exception_failure_info(exc)
    if job_log_started:
        return {
            'failure_stage': 'persistence',
            'fail_reason': exception_fail_reason(exc),
            'transport_state': 'prepared',
        }
    return {
        'failure_stage': 'pre_request',
        'fail_reason': exception_fail_reason(exc),
        'transport_state': 'not_started',
    }


def is_timeout_exception(exc):
    return isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout))


def pre_request_outcome(content):
    """未发起 HTTP 请求时的 status / fail_reason。"""
    text = (content or '').strip()
    if text.startswith(BLOCKED_URL_PREFIXES):
        return STATUS_ERROR, 'blocked_url'
    if text in ('定时任务不存在', '请求链接不存在', '请求链接有误，请检查一下'):
        return STATUS_ERROR, 'internal'
    if text.startswith('发生严重错误'):
        return STATUS_ERROR, 'internal'
    return None, None


def should_alert(status):
    return status in (STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT)
