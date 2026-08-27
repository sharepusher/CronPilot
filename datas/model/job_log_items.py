#!/usr/bin/python3
# -*- coding:utf-8 -*-
from sqlalchemy.orm import Mapped, mapped_column

from app import db


class JobLogItems(db.Model):
    __tablename__ = 'job_log_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    trace_id: Mapped[str] = mapped_column('trace_id', db.String(65), index=True, nullable=False)
    content: Mapped[str] = mapped_column(db.TEXT, nullable=False, default='')
