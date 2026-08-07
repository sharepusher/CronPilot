#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""任务 ↔ 业务资源组多对多（OPT-P1-11）。

scope_type='GROUP' 的任务通过此表关联可见业务组；
scope_type='GLOBAL' 的任务无需此表记录，全局可见。
"""

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class TaskGroup(db.Model):
    __tablename__ = 'task_groups'
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('task_id', 'group_id', name='uq_task_groups_task_group'),
    )
