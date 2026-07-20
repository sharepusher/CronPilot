#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""用户 ↔ 业务资源组多对多（OPT-P2-12）。"""

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class UserGroup(db.Model):
    __tablename__ = 'user_groups'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'group_id', name='uq_user_groups_user_group'),
    )
