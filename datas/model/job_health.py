#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""任务健康聚合表（OPT-P2-13）：列表/Metric 读此表，勿每次扫 job_log。"""

from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class JobHealth(db.Model):
    __tablename__ = 'job_health'
    cron_info_id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    last_run_at: Mapped[int] = mapped_column(db.BigInteger, nullable=False, default=0)
    last_run_status: Mapped[Optional[str]] = mapped_column(db.String(16), nullable=True)
    last_run_log_id: Mapped[str] = mapped_column(
        db.String(65), nullable=False, default=''
    )
    last_success_at: Mapped[int] = mapped_column(
        db.BigInteger, nullable=False, default=0
    )
    last_fail_at: Mapped[int] = mapped_column(db.BigInteger, nullable=False, default=0)
    consecutive_failures: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=0
    )
    health_status: Mapped[str] = mapped_column(
        db.String(16),
        nullable=False,
        default='unknown',
        doc='ok | failing | unknown',
    )
    updated_at: Mapped[int] = mapped_column(db.BigInteger, nullable=False, default=0, index=True)
