#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""任务 ↔ 标签多对多（OPT-P1-11）。"""

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class TaskTag(db.Model):
    __tablename__ = 'task_tags'
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('task_id', 'tag_id', name='uq_task_tags_task_tag'),
    )
