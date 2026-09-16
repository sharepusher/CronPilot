# -*- coding: utf-8 -*-
"""Presentation-only transformation for the execution inspector timeline."""
import json
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services.job_log_display import job_log_badge
from datas.utils.times import hms_to_display

_EVENT_LABELS = {
    'task.enqueued': '已入队',
    'task.start': '开始执行',
    'db.load_cif': '读取任务配置',
    'ssrf.check': '安全校验',
    'http.start': '发送 HTTP 请求',
    'http.complete': 'HTTP 请求完成',
    'http.timeout': 'HTTP 请求超时',
    'http.error': 'HTTP 请求异常',
    'db.write_log': '写入执行记录',
}

_FAIL_REASON_LABELS = {
    'http_4xx': 'HTTP 4xx',
    'http_5xx': 'HTTP 5xx',
    'keyword': '关键词匹配',
    'timeout': '请求超时',
    'connection': '连接失败',
    'blocked_url': 'URL 拦截',
    'internal': '内部错误',
}
_TRIGGER_LABELS = {
    'schedule': '定时调度',
    'manual': '手动执行',
    'one_shot': '一次性任务',
}


def sanitize_url_for_display(raw_url):
    """Return a fail-closed URL safe for every execution-detail role.

    A configured URL is untrusted display data: arbitrary query keys can hold
    credentials, so preserve key names and order but never preserve values.
    """
    if not raw_url:
        return '—'
    try:
        parts = urlsplit(str(raw_url))
        host = parts.hostname
        if not parts.scheme or not host:
            return '地址格式异常（已隐藏）'
        if ':' in host and not host.startswith('['):
            host = '[{}]'.format(host)
        port = parts.port
        netloc = host if port is None else '{}:{}'.format(host, port)
        if parts.username is not None or parts.password is not None:
            netloc = '***:***@' + netloc
        raw_query = parts[3]
        query_text = urlencode(
            [(key, '***') for key, _value in parse_qsl(raw_query, keep_blank_values=True)],
            doseq=True,
            safe='*',
        )
        return urlunsplit((parts.scheme, netloc, parts.path, query_text, ''))
    except (TypeError, ValueError):
        return '地址格式异常（已隐藏）'


def _display_time(epoch_ms):
    try:
        return datetime.fromtimestamp(int(epoch_ms) / 1000).strftime('%H:%M:%S.%f')[:-3]
    except (TypeError, ValueError, OSError, OverflowError):
        return '—'


def _detail_value(raw, include_detail):
    if not include_detail:
        return ''
    try:
        parsed = json.loads(raw or '{}')
    except (TypeError, ValueError):
        return ''
    return json.dumps(parsed, ensure_ascii=False, sort_keys=True)


def build_event_timeline(events, include_detail=False):
    """Return template-safe event rows; only admins receive structured detail."""
    rows = []
    for event in events:
        rows.append({
            'seq': event.seq,
            'time': _display_time(event.occurred_at_ms),
            'offset_ms': event.offset_ms,
            'label': _EVENT_LABELS.get(event.event_type, event.event_type),
            'outcome': event.outcome,
            'detail': _detail_value(event.detail, include_detail),
        })
    return rows


def _display_hms(value):
    displayed = hms_to_display(value)
    if displayed:
        return displayed
    return str(value) if isinstance(value, str) and value else '—'


def _duration_display(value):
    try:
        seconds = float(value or 0)
    except (TypeError, ValueError):
        return '—'
    if seconds >= 1:
        return '{:.1f}s'.format(seconds)
    if seconds > 0:
        return '{}ms'.format(int(seconds * 1000))
    return '—'


def build_run_inspector_view(
    job_log,
    cron_info,
    *,
    group_name='',
    schedule_display='',
    timeline=None,
    business_items=None,
    is_admin=False,
):
    """Build the only data shape the Run Inspector template may consume."""
    if job_log is None:
        return {'exists': False, 'id': '—', 'task': None, 'timeline': []}

    status = job_log.status or ''
    badge_label, badge_tone = job_log_badge(status)
    if status == 'running':
        badge_label, badge_tone = '◎ 执行中 · 最终结果未知', 'running'
    elif status == 'pending':
        badge_label, badge_tone = '○ 已入队 · 最终结果未知', 'pending'
    elif not badge_label:
        badge_label, badge_tone = status or '未知', 'pending'
    trigger_source = job_log.trigger_source or 'schedule'
    raw_response = job_log.content or '无响应内容'
    return {
        'exists': True,
        'id': job_log.id,
        'status_tone': badge_tone,
        'status_label': badge_label,
        'task': {
            'id': cron_info.id if cron_info else None,
            'name': cron_info.task_name if cron_info else '—',
        },
        'summary': {
            'http_status': job_log.http_status or '—',
            'duration': _duration_display(job_log.take_time),
            'is_timeout': status == 'timeout',
            'started_at': _display_hms(job_log.started_at or job_log.create_time),
            'finished_at': _display_hms(job_log.finished_at),
            'has_finished_at': bool(job_log.finished_at),
            'trigger_type': _TRIGGER_LABELS.get(trigger_source, trigger_source),
            'fail_reason': _FAIL_REASON_LABELS.get(job_log.fail_reason, job_log.fail_reason or ''),
        },
        'request': {
            'method': (getattr(cron_info, 'req_method', None) or 'GET').upper(),
            'display_url': sanitize_url_for_display(getattr(cron_info, 'req_url', None)),
            'actual_request_sent': bool(job_log.actual_url) if is_admin else False,
        },
        'response': {
            'http_status': job_log.http_status,
            'is_success': status == 'success',
            'body_visible': is_admin,
            'display_body': raw_response if is_admin else '响应正文与异常详情仅管理员可见。',
        },
        'business_logs': {
            'visible': is_admin,
            'entries': [item.content for item in (business_items or [])] if is_admin else [],
        },
        'metadata': {
            'group_name': group_name or '全局',
            'schedule_display': schedule_display,
            'trace_id': job_log.trace_id or '—',
            'timeout_sec': job_log.timeout_sec or 5,
            'trigger_delay_ms': job_log.trigger_delay_ms,
        },
        'timeline': timeline or [],
    }
