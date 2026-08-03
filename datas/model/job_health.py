#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""任务健康聚合表（OPT-P2-13）：列表/Metric 读此表，勿每次扫 job_log。"""

from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class JobHealth(db.Model):
    __tablename__ = 'job_health'
    cron_info_id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    last_run_at: Mapped[str] = mapped_column(db.String(25), nullable=False, default='')
    last_run_status: Mapped[Optional[str]] = mapped_column(db.String(16), nullable=True)
    last_run_log_id: Mapped[str] = mapped_column(
        db.String(65), nullable=False, default=''
    )
    last_success_at: Mapped[str] = mapped_column(
        db.String(25), nullable=False, default=''
    )
    last_fail_at: Mapped[str] = mapped_column(db.String(25), nullable=False, default='')
    consecutive_failures: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=0
    )
    health_status: Mapped[str] = mapped_column(
        db.String(16),
        nullable=False,
        default='unknown',
        doc='ok | failing | unknown',
    )
    updated_at: Mapped[str] = mapped_column(db.String(25), nullable=False, default='', index=True)
