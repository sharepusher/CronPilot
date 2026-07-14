#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""用户 ↔ 业务资源组多对多（OPT-P2-12）。"""

from app import db


class UserGroup(db.Model):
    __tablename__ = 'user_groups'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    group_id = db.Column(db.Integer, nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'group_id', name='uq_user_groups_user_group'),
    )
