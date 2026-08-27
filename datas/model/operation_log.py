#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""管理端业务变更审计（OPT-P1-09）。与 rbac_audit_logs 分表。"""

from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class OperationLog(db.Model):
    __tablename__ = 'operation_log'
    id: Mapped[int] = mapped_column(primary_key=True)
    create_time: Mapped[int] = mapped_column(
        db.BigInteger, nullable=False, default=0, index=True
    )
    action: Mapped[str] = mapped_column(db.String(32), nullable=False, default='')
    channel: Mapped[str] = mapped_column(db.String(8), nullable=False, default='')
    operator_type: Mapped[str] = mapped_column(db.String(16), nullable=False, default='')
    operator_id: Mapped[str] = mapped_column(
        db.String(64), nullable=False, default='', index=True
    )
    operator_name: Mapped[str] = mapped_column(
        db.String(120), nullable=False, default='', index=True
    )
    operator_roles_json: Mapped[str] = mapped_column(
        db.TEXT, nullable=False, default=''
    )
    operator_permissions_json: Mapped[str] = mapped_column(
        db.TEXT, nullable=False, default=''
    )
    client_ip: Mapped[str] = mapped_column(db.String(45), nullable=False, default='')
    target_type: Mapped[str] = mapped_column(
        db.String(16), nullable=False, default='cron'
    )
    target_id: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    task_name: Mapped[str] = mapped_column(
        db.String(120), nullable=False, default='', index=True
    )
    detail_json: Mapped[str] = mapped_column(db.TEXT, nullable=False, default='')
    result: Mapped[str] = mapped_column(db.String(8), nullable=False, default='ok')
    error_msg: Mapped[str] = mapped_column(db.String(255), nullable=False, default='')
