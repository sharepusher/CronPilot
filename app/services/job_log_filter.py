# -*- coding:utf-8 -*-
"""执行记录 outcome 筛选（OPT-P1-01c）。"""
from app.services.job_log_outcome import (
    STATUS_ERROR,
    STATUS_FAIL,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
)
from datas.model.job_log import JobLog

# 视图层 URL 白名单须与此集合对齐（含 in_progress）；新增 outcome 时两处同步
KNOWN_OUTCOMES = frozenset({
    'success', 'fail', 'error', 'not_success', 'unknown', 'exception',
    'in_progress', 'all',
})


def job_log_outcome_clause(outcome):
    """outcome → SQL 条件；非法/全部返回 None。"""
    o = (outcome or '').strip().lower()
    if o in ('', 'all'):
        return None
    if o == 'success':
        return JobLog.status == STATUS_SUCCESS
    if o == 'fail':
        return JobLog.status == STATUS_FAIL
    if o == 'error':
        return JobLog.status == STATUS_ERROR
    if o == 'exception':
        return JobLog.status.in_((STATUS_ERROR, STATUS_TIMEOUT))
    if o == 'not_success':
        # 仅终态失败类；不含 pending/running（默认「非成功」语义不变）
        return JobLog.status.in_((STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT))
    if o == 'in_progress':
        return JobLog.status.in_((STATUS_PENDING, STATUS_RUNNING))
    if o == 'unknown':
        return JobLog.status.is_(None)
    return None
