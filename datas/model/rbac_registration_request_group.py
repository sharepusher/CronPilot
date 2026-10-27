#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""注册申请单 ↔ 业务资源组关联（R2-2）。"""

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class RbacRegistrationRequestGroup(db.Model):
    __tablename__ = 'rbac_registration_request_groups'

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_request_id: Mapped[int] = mapped_column(
        db.Integer, nullable=False,
    )
    group_id: Mapped[int] = mapped_column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            'registration_request_id',
            'group_id',
            name='uq_reg_req_groups_req_group',
        ),
        db.Index(
            'ix_reg_req_groups_group_req',
            'group_id',
            'registration_request_id',
        ),
    )
