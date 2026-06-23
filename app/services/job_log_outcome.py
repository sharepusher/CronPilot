# -*- coding:utf-8 -*-
"""job_log 执行成败判定（OPT-P1-01/02）。"""

import requests

STATUS_SUCCESS = 'success'
STATUS_FAIL = 'fail'
STATUS_ERROR = 'error'


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
    if fail_on_http_4xx_5xx_enabled(fail_on_http_flag):
        if code >= 500:
            return STATUS_FAIL, 'http_5xx'
        if code >= 400:
            return STATUS_FAIL, 'http_4xx'
    if keyword_matched(body, error_keyword):
        return STATUS_FAIL, 'keyword'
    return STATUS_SUCCESS, None


def exception_fail_reason(exc):
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout)):
        return 'timeout'
    if isinstance(
        exc,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.SSLError,
            requests.exceptions.TooManyRedirects,
        ),
    ):
        return 'connection'
    return 'internal'


def pre_request_outcome(content):
    """未发起 HTTP 请求时的 status / fail_reason。"""
    text = (content or '').strip()
    if text.startswith('回调URL安全校验未通过'):
        return STATUS_ERROR, 'blocked_url'
    if text in ('定时任务不存在', '请求链接不存在', '请求链接有误，请检查一下'):
        return STATUS_ERROR, 'internal'
    if text.startswith('发生严重错误'):
        return STATUS_ERROR, 'internal'
    return None, None


def should_alert(status):
    return status in (STATUS_FAIL, STATUS_ERROR)
