#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""任务健康聚合表（OPT-P2-13）：列表/Metric 读此表，勿每次扫 job_log。"""

from app import db


class JobHealth(db.Model):
    __tablename__ = 'job_health'
    cron_info_id = db.Column(db.Integer, primary_key=True)
    last_run_at = db.Column(db.String(25), nullable=False, default='')
    last_run_status = db.Column(db.String(16), nullable=True)
    last_run_log_id = db.Column(db.String(65), nullable=False, default='')
    last_success_at = db.Column(db.String(25), nullable=False, default='')
    last_fail_at = db.Column(db.String(25), nullable=False, default='')
    consecutive_failures = db.Column(db.Integer, nullable=False, default=0)
    health_status = db.Column(
        db.String(16),
        nullable=False,
        default='unknown',
        doc='ok | failing | unknown',
    )
    updated_at = db.Column(db.String(25), nullable=False, default='')
