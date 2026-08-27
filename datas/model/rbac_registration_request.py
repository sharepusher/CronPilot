#!/usr/bin/python3
# -*- coding:utf-8 -*-

from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app import db
from app.auth.password import hash_password


class RbacRegistrationRequest(db.Model):
    """用户注册申请（OPT-P1-10）。"""
    __tablename__ = 'rbac_registration_requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(db.String(128), nullable=False, index=True)
    username: Mapped[str] = mapped_column(db.String(64), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    role: Mapped[str] = mapped_column(db.String(20), nullable=False, default='viewer')
    group_ids: Mapped[str] = mapped_column(db.String(255), nullable=False, default='')
    # OPT-P1-10：岗位类型（tech/ops/qa/pm/proj_mgr/strategy/operation/other:xxx）
    job_title: Mapped[str] = mapped_column(db.String(64), nullable=False, default='')
    # OPT-P1-10：花名
    nickname: Mapped[str] = mapped_column(db.String(64), nullable=False, default='')
    reason: Mapped[str] = mapped_column(db.String(500), nullable=False, default='')
    status: Mapped[str] = mapped_column(
        db.String(20), nullable=False, default='pending', index=True
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    review_comment: Mapped[Optional[str]] = mapped_column(
        db.String(500), nullable=True, default=None
    )
    create_time: Mapped[int] = mapped_column(
        db.BigInteger, nullable=False, default=0, index=True
    )
    update_time: Mapped[Optional[int]] = mapped_column(
        db.BigInteger, nullable=True, default=None
    )
    # 竞态防护：pending 状态时设为 username，其他状态设为 NULL。
    # UNIQUE 索引保证同一 username 只能有一条 pending 记录。
    # NULL 不参与唯一约束，因此已处理的记录不会冲突。
    pending_username: Mapped[Optional[str]] = mapped_column(
        db.String(64), nullable=True, unique=True, default=None
    )

    def set_password(self, plain):
        self.password_hash = hash_password(plain)
