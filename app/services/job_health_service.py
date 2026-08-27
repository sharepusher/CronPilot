# -*- coding:utf-8 -*-
"""任务健康写路径（OPT-P2-13 B0）。

N = health_failing_threshold：连续失败达到 N 次才标 failing（默认 3）。
失败 / 状态翻转同步写；连续成功可节流，降低秒级任务行锁压力。
"""
from __future__ import absolute_import

from configs import configs
from app import db
from app.services.job_log_outcome import STATUS_ERROR, STATUS_FAIL, STATUS_SUCCESS, STATUS_TIMEOUT
from datas.model.job_health import JobHealth

HEALTH_OK = 'ok'
HEALTH_FAILING = 'failing'
HEALTH_UNKNOWN = 'unknown'

# 连续成功时，距上次 updated_at 不足该秒数则跳过写库
SUCCESS_THROTTLE_SECONDS = 10

DEFAULT_FAILING_THRESHOLD = 3


def get_failing_threshold(cron_config=None):
    """解析 conf health_failing_threshold；非法或缺失时返回 3。"""
    raw = None
    if cron_config is not None:
        raw = cron_config.get('health_failing_threshold')
    if raw is None or raw == '':
        try:
            raw = configs('health_failing_threshold')
        except Exception:
            raw = None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_FAILING_THRESHOLD
    if n < 1:
        return DEFAULT_FAILING_THRESHOLD
    return n


def _parse_time_to_epoch(timestr):
    """BIGINT 百毫秒 → epoch 秒；兼容旧格式字符串。解析失败返回 None。"""
    if not timestr:
        return None
    try:
        val = int(timestr)
        if val <= 0:
            return None
        return val / 10.0
    except (ValueError, TypeError):
        pass
    try:
        import time
        return time.mktime(time.strptime(str(timestr)[:19], '%Y-%m-%d %H:%M:%S'))
    except Exception:
        return None


def _should_throttle_success(prev_updated_at, now_at, throttle_seconds=SUCCESS_THROTTLE_SECONDS):
    prev = _parse_time_to_epoch(prev_updated_at)
    now = _parse_time_to_epoch(now_at)
    if prev is None or now is None:
        return False
    return (now - prev) < throttle_seconds


def update_job_health(cron_info_id, outcome, at, log_id='', threshold=None, cron_config=None):
    """根据单次 Run outcome 更新 job_health；返回 JobHealth 或 None。"""
    if not cron_info_id:
        return None
    if outcome not in (STATUS_SUCCESS, STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT):
        return None

    n = threshold if threshold is not None else get_failing_threshold(cron_config)
    row = db.session.get(JobHealth, int(cron_info_id))
    if row is None:
        row = JobHealth(
            cron_info_id=int(cron_info_id),
            consecutive_failures=0,
            health_status=HEALTH_UNKNOWN,
        )
        db.session.add(row)

    if outcome in (STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT):
        row.consecutive_failures = int(row.consecutive_failures or 0) + 1
        row.last_fail_at = at or ''
        row.last_run_at = at or ''
        row.last_run_status = outcome
        row.last_run_log_id = log_id or ''
        row.health_status = (
            HEALTH_FAILING if row.consecutive_failures >= n else HEALTH_OK
        )
        row.updated_at = at or ''
        db.session.commit()
        return row

    # success
    prev_status = row.last_run_status
    prev_fail = int(row.consecutive_failures or 0)
    if prev_fail > 0 or prev_status != STATUS_SUCCESS:
        row.consecutive_failures = 0
        row.last_success_at = at or ''
        row.last_run_at = at or ''
        row.last_run_status = STATUS_SUCCESS
        row.last_run_log_id = log_id or ''
        row.health_status = HEALTH_OK
        row.updated_at = at or ''
        db.session.commit()
        return row

    if _should_throttle_success(row.updated_at, at):
        return row

    row.last_run_at = at or ''
    row.last_run_status = STATUS_SUCCESS
    row.last_run_log_id = log_id or ''
    row.health_status = HEALTH_OK
    row.updated_at = at or ''
    db.session.commit()
    return row
