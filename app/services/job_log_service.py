# -*- coding: utf-8 -*-
"""执行日志清理（供 crons 与 cron 删除使用，避免与 cron_service 循环依赖）。"""
from sqlalchemy import delete, func, select

from app import db
from datas.model.job_log import JobLog


def delete_job_logs_for_cron(cron_id):
    db.session.execute(
        delete(JobLog).where(JobLog.cron_info_id == cron_id)
    )


def trim_job_logs_for_cron(cron_info_id, keep_count):
    total = db.session.scalar(
        select(func.count())
        .select_from(JobLog)
        .where(JobLog.cron_info_id == cron_info_id)
    ) or 0
    excess = total - keep_count
    if excess <= 0:
        return
    ids = list(
        db.session.scalars(
            select(JobLog.id)
            .where(JobLog.cron_info_id == cron_info_id)
            .order_by(JobLog.id.asc())
            .limit(excess)
        )
    )
    if ids:
        db.session.execute(delete(JobLog).where(JobLog.id.in_(ids)))
