# -*- coding: utf-8 -*-
"""不可变的任务执行阶段事件。"""
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class JobLogEvent(db.Model):
    __tablename__ = 'job_log_events'

    id: Mapped[int] = mapped_column(
        db.BigInteger().with_variant(db.Integer, 'sqlite'),
        primary_key=True,
        autoincrement=True,
    )
    trace_id: Mapped[str] = mapped_column(db.String(65), nullable=False, index=True)
    run_id: Mapped[Optional[int]] = mapped_column(db.BigInteger, nullable=True, index=True)
    cron_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    seq: Mapped[int] = mapped_column(db.Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(db.String(48), nullable=False)
    occurred_at_ms: Mapped[int] = mapped_column(db.BigInteger, nullable=False)
    offset_ms: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    duration_ms: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(db.String(16), nullable=False, default='ok')
    detail: Mapped[str] = mapped_column(db.TEXT, nullable=False, default='{}')
    schema_version: Mapped[int] = mapped_column(db.SmallInteger, nullable=False, default=1)

    __table_args__ = (
        db.UniqueConstraint('trace_id', 'seq', name='uq_job_log_events_trace_seq'),
        db.UniqueConstraint('run_id', 'seq', name='uq_job_log_events_run_seq'),
    )
