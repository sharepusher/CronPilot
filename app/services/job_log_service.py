# -*- coding:utf-8 -*-
"""执行日志清理（供 crons 与 cron 删除使用，避免与 cron_service 循环依赖）。"""
from app import db
from datas.model.job_log import JobLog


def delete_job_logs_for_cron(cron_id):
    JobLog.query.filter(JobLog.cron_info_id == cron_id).delete(synchronize_session=False)


def trim_job_logs_for_cron(cron_info_id, keep_count):
    excess = JobLog.query.filter(JobLog.cron_info_id == cron_info_id).count() - keep_count
    if excess <= 0:
        return
    ids = [
        row[0]
        for row in db.session.query(JobLog.id)
        .filter(JobLog.cron_info_id == cron_info_id)
        .order_by(JobLog.id.asc())
        .limit(excess)
        .all()
    ]
    if ids:
        JobLog.query.filter(JobLog.id.in_(ids)).delete(synchronize_session=False)
