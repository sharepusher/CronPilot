# -*- coding:utf-8 -*-
"""执行记录 outcome 筛选（OPT-P1-01c）。"""
from datas.model.job_log import JobLog
from app.services.job_log_outcome import STATUS_ERROR, STATUS_FAIL, STATUS_SUCCESS, STATUS_TIMEOUT


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
        return JobLog.status.in_((STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT))
    if o == 'unknown':
        return JobLog.status.is_(None)
    return None
