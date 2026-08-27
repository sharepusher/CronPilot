#!/usr/bin/python3
# -*- coding:utf-8 -*-

from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class RbacAuditLog(db.Model):
    __tablename__ = 'rbac_audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    username: Mapped[str] = mapped_column(db.String(64), nullable=False, default='')
    action: Mapped[str] = mapped_column(db.String(64), nullable=False, default='')
    resource: Mapped[str] = mapped_column(db.String(128), nullable=False, default='')
    ip: Mapped[str] = mapped_column(db.String(64), nullable=False, default='')
    status: Mapped[str] = mapped_column(db.String(16), nullable=False, default='allow')
    create_time: Mapped[int] = mapped_column(db.BigInteger, nullable=False, default=0, index=True)
    actor_group_ids: Mapped[str] = mapped_column(db.String(255), nullable=False, default='')
