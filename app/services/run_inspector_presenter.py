# -*- coding: utf-8 -*-
"""Presentation-only transformation for the execution inspector timeline.

Write-path detail whitelist: ``app.services.execution_tracer._DETAIL_KEYS``.
Contract gate: ``tests/test_execution_observability_contract.py``.
Readable summary keys must stay a subset of the Tracer whitelist (R3).
"""
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

# Keys the summary path may read from event.detail (⊆ Tracer._DETAIL_KEYS).
# Empty set = fixed phrase only; never surface exc_detail / block_detail text.
_SUMMARY_KEYS = {
    'task.enqueued': frozenset({'trigger_source', 'scheduled_delay_ms', 'scheduled_at'}),
    'http.start': frozenset({'method', 'display_url', 'timeout_sec', 'transport_state', 'response_received'}),
    'http.complete': frozenset({'http_status', 'response_bytes', 'transport_state', 'response_received'}),
    'ssrf.check': frozenset({'block_type'}),
    'http.timeout': frozenset({'failure_stage', 'fail_reason', 'transport_state', 'response_received'}),
    'http.error': frozenset({'failure_stage', 'fail_reason', 'transport_state', 'response_received'}),
    'db.write_log': frozenset({'status'}),
}

# Runtime emit set from app.crons cron_do (must ⊆ _EVENT_LABELS).
_EMITTED_EVENT_TYPES = frozenset({
    'task.enqueued',
    'task.start',
    'db.load_cif',
    'ssrf.check',
    'http.start',
    'http.complete',
    'http.timeout',
    'http.error',
    'db.write_log',
})

_FAIL_REASON_LABELS = {
    'http_4xx': 'HTTP 4xx',
    'http_5xx': 'HTTP 5xx',
    'keyword': '关键词匹配',
    'timeout': '请求超时',
    'connection': '连接失败',
    'client_incompatible': 'HTTP 客户端初始化失败',
    'blocked_url': 'URL 拦截',
    'internal': '内部错误',
}
_FAILURE_STAGE_LABELS = {
    'pre_request': '请求前置',
    'transport': '传输层',
    'remote_response': '远端响应',
    'persistence': '记录持久化',
}
_TRIGGER_LABELS = {
    'schedule': '定时调度',
    'manual': '手动执行',
    'one_shot': '一次性任务',
}

_VIEWER_ROLES = frozenset({'viewer', 'operator', 'admin'})
_OPERATOR_BODY_LIMIT = 200
_ADMIN_BODY_LIMIT = 2048


def normalize_viewer_role(role):
    """Map session role to Presenter viewer_role (viewer / operator / admin)."""
    value = (role or '').strip().lower()
    if value in _VIEWER_ROLES:
        return value
    return 'viewer'


def sanitize_url_for_display(raw_url, *, strip_query=False):
    """Return a fail-closed URL safe for every execution-detail role.

    A configured URL is untrusted display data: arbitrary query keys can hold
    credentials, so preserve key names and order but never preserve values.
    Viewer may strip the entire query string (R2 contract).
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
        if strip_query:
            return urlunsplit((parts.scheme, netloc, parts.path, '', ''))
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


def _parse_detail(raw):
    try:
        parsed = json.loads(raw or '{}')
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _event_summary(event_type, outcome, raw_detail, viewer_role):
    """Whitelist short summary only — never raw JSON / exc_detail text."""
    allowed = _SUMMARY_KEYS.get(event_type)
    if allowed is None:
        return ''
    raw_parsed = _parse_detail(raw_detail)
    parsed = {
        key: value for key, value in raw_parsed.items()
        if key in allowed
    }
    if event_type == 'http.start':
        method = parsed.get('method')
        parts = [str(method).upper()] if method else []
        if parsed.get('display_url'):
            parts.append(str(parsed['display_url']))
        if parsed.get('timeout_sec'):
            parts.append('阈值 {}s'.format(parsed['timeout_sec']))
        return ' · '.join(parts)
    if event_type == 'task.enqueued':
        source = parsed.get('trigger_source') or ''
        delay = parsed.get('scheduled_delay_ms')
        text = '已入队'
        if source:
            text += ' · {}'.format(_TRIGGER_LABELS.get(source, source))
        if delay is not None:
            text += ' · 延迟 {}ms'.format(delay)
        return text
    if event_type == 'http.complete':
        status = parsed.get('http_status')
        if status is None or status == '':
            return ''
        suffix = ''
        if parsed.get('response_bytes') is not None:
            suffix = ' · {}B'.format(parsed['response_bytes'])
        return 'HTTP {}{}'.format(status, suffix)
    if event_type == 'ssrf.check' and outcome in ('blocked', 'fail', 'error'):
        block_type = parsed.get('block_type')
        if block_type and viewer_role != 'viewer':
            return '拦截：{}'.format(block_type)
        return '已拦截'
    if event_type == 'http.timeout':
        return '等待超过阈值'
    if event_type == 'http.error':
        if viewer_role == 'viewer':
            return '请求异常'
        reason = parsed.get('fail_reason')
        if not reason and raw_parsed.get('exc_type') == 'TypeError' and 'assert_hostname' in str(raw_parsed.get('exc_detail') or ''):
            reason = 'client_incompatible'
        return _FAIL_REASON_LABELS.get(reason, '请求异常')
    if event_type == 'db.write_log' and viewer_role != 'viewer':
        status = parsed.get('status')
        return str(status) if status else ''
    return ''


def build_event_timeline(events, viewer_role='viewer'):
    """Return template-safe event rows; never include raw detail JSON."""
    role = normalize_viewer_role(viewer_role)
    rows = []
    for event in events:
        rows.append({
            'seq': event.seq,
            'time': _display_time(event.occurred_at_ms),
            'offset_ms': event.offset_ms,
            'label': _EVENT_LABELS.get(event.event_type, event.event_type),
            'outcome': event.outcome,
            'summary': _event_summary(
                event.event_type, event.outcome, event.detail, role,
            ),
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


def _truncate_text(text, limit):
    value = text if isinstance(text, str) else (str(text) if text is not None else '')
    if len(value) <= limit:
        return value
    return value[:limit] + '…'


def _response_display(raw_response, viewer_role):
    if viewer_role == 'viewer':
        return '无权限查看正文', False
    if viewer_role == 'operator':
        return _truncate_text(raw_response, _OPERATOR_BODY_LIMIT), True
    return _truncate_text(raw_response, _ADMIN_BODY_LIMIT), True


def build_run_inspector_view(
    job_log,
    cron_info,
    *,
    group_name='',
    schedule_display='',
    timeline=None,
    business_items=None,
    viewer_role='viewer',
    is_admin=None,
):
    """Build the only data shape the Run Inspector template may consume.

    ``is_admin`` is accepted only as a deprecated alias for
    ``viewer_role='admin'`` when True; prefer ``viewer_role``.
    """
    if is_admin is True:
        viewer_role = 'admin'
    role = normalize_viewer_role(viewer_role)

    if job_log is None:
        return {
            'exists': False,
            'id': '—',
            'task': None,
            'timeline': [],
            'is_incomplete': False,
            'status': '',
        }

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
    display_body, body_visible = _response_display(raw_response, role)
    is_incomplete = status in ('pending', 'running')
    collapse_downstream = status == 'success'
    strip_query = role == 'viewer'
    return {
        'exists': True,
        'id': job_log.id,
        'status': status,
        'status_tone': badge_tone,
        'status_label': badge_label,
        'is_incomplete': is_incomplete,
        'observability_state': getattr(job_log, 'observability_state', None) or 'unknown',
        'observability_drop_reason': getattr(job_log, 'observability_drop_reason', None) or '',
        'collapse_downstream': collapse_downstream,
        'task': {
            'id': cron_info.id if cron_info else None,
            'name': cron_info.task_name if cron_info else '—',
        },
        'summary': {
            'http_status': job_log.http_status or '—',
            'http_status_label': (
                '未获得 HTTP 响应' if not job_log.http_status and getattr(job_log, 'response_received', None) is False
                else (job_log.http_status or '—')
            ),
            'duration': _duration_display(job_log.take_time),
            'is_timeout': status == 'timeout',
            'started_at': _display_hms(job_log.started_at or job_log.create_time),
            'finished_at': _display_hms(job_log.finished_at),
            'has_finished_at': bool(job_log.finished_at),
            'trigger_type': _TRIGGER_LABELS.get(trigger_source, trigger_source),
            'fail_reason': _FAIL_REASON_LABELS.get(job_log.fail_reason, job_log.fail_reason or ''),
            'failure_stage': _FAILURE_STAGE_LABELS.get(
                getattr(job_log, 'failure_stage', None),
                getattr(job_log, 'failure_stage', None) or '',
            ),
            'transport_state': getattr(job_log, 'transport_state', None) or '',
            'response_received': getattr(job_log, 'response_received', None),
        },
        'request': {
            'method': (getattr(cron_info, 'req_method', None) or 'GET').upper(),
            'display_url': sanitize_url_for_display(
                getattr(cron_info, 'req_url', None),
                strip_query=strip_query,
            ),
            'actual_request_sent': (
                role == 'admin' and getattr(job_log, 'transport_state', None) in ('sent', 'response_received')
            ),
            'parameter_prepared': bool(job_log.actual_url) if role == 'admin' else False,
        },
        'response': {
            'http_status': job_log.http_status,
            'is_success': status == 'success',
            'body_visible': body_visible,
            'display_body': display_body,
        },
        'business_logs': {
            'visible': role == 'admin',
            'entries': (
                [item.content for item in (business_items or [])]
                if role == 'admin' else []
            ),
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
