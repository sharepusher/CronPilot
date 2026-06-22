# -*- coding:utf-8 -*-
"""job_log 列表/详情展示辅助（方案 A′）。"""


def job_log_status_line(http_status, content):
    """第一行：HTTP 状态或异常摘要。"""
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


def job_log_content_preview(content, limit=120):
    text = content or ''
    if len(text) <= limit:
        return text
    return text[:limit] + '…'
