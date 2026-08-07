#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""业务/服务标签（OPT-P1-11）。

用户创建任务时可自由输入标签（国家/业务线/服务名等），
系统自动去重入库；管理员可新建、编辑（含说明）、删除。
"""

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class Tag(db.Model):
    __tablename__ = 'tags'
    __table_args__ = (
        db.UniqueConstraint('name', 'group_id', name='uix_tag_name_group'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        db.String(64), nullable=False, index=True
    )
    group_id = mapped_column(db.Integer, nullable=True, index=True)
    description: Mapped[str] = mapped_column(
        db.String(255), nullable=False, default=''
    )
    created_by: Mapped[str] = mapped_column(
        db.String(120), nullable=False, default=''
    )
    create_time: Mapped[str] = mapped_column(
        db.String(25), nullable=False, default='', index=True
    )
    update_time: Mapped[str] = mapped_column(
        db.String(25), nullable=False, default='', index=True
    )
