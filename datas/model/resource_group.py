#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""业务资源组（OPT-P2-12 Resource Scope）。与 RBAC 角色解耦。"""

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class ResourceGroup(db.Model):
    __tablename__ = 'resource_groups'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(64), nullable=False, default='')
    code: Mapped[str] = mapped_column(
        db.String(64), nullable=False, unique=True, index=True
    )
    description: Mapped[str] = mapped_column(
        db.String(255), nullable=False, default=''
    )
    create_time: Mapped[str] = mapped_column(db.String(25), nullable=False, default='', index=True)
