# -*- coding:utf-8 -*-
"""job_log 列表/详情展示辅助（方案 A′ + P1 徽章）。"""

from app.services.job_log_outcome import (
    STATUS_ERROR,
    STATUS_FAIL,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
)


def job_log_status_line(http_status, content):
    """第一行：HTTP 状态或异常摘要（色调用于无 status 旧数据）。"""
    if http_status is not None and int(http_status) > 0:
        code = int(http_status)
        if code >= 500:
            return 'HTTP %s' % code, 'fail'
        if code >= 400:
            return 'HTTP %s' % code, 'warn'
        return 'HTTP %s' % code, 'ok'
    text = (content or '').strip()
    if text.startswith('发生严重错误'):
        return '请求异常', 'fail'
    if text.startswith('回调URL安全校验未通过') or text in (
        '定时任务不存在',
        '请求链接不存在',
        '请求链接有误，请检查一下',
    ):
        return '未执行回调', 'muted'
    if text:
        return '—', 'muted'
    return '—', 'muted'


def job_log_badge(status):
    """徽章文案与色调（兼容旧值 + B1 新状态机值）。"""
    if status == STATUS_SUCCESS:
        return '成功', 'ok'
    if status == STATUS_FAIL:
        return '失败', 'fail'
    if status == STATUS_ERROR:
        return '异常', 'error'
    if status == STATUS_TIMEOUT:
        return '超时', 'timeout'
    if status == STATUS_RUNNING:
        return '执行中', 'running'
    if status == STATUS_PENDING:
        return '待执行', 'pending'
    return None, None


def job_log_status_badge_class(status):
    """返回 Bootstrap label CSS class（用于列表 badge）。"""
    mapping = {
        STATUS_SUCCESS: 'label-success',
        STATUS_FAIL: 'label-danger',
        STATUS_ERROR: 'label-warning',
        STATUS_TIMEOUT: 'label-timeout',
        STATUS_RUNNING: 'label-running',
        STATUS_PENDING: 'label-pending',
    }
    return mapping.get(status or '', 'label-default')


def job_log_content_preview(content, limit=120):
    text = content or ''
    if len(text) <= limit:
        return text
    return text[:limit] + '…'
