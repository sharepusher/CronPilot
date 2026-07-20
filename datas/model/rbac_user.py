#!/usr/bin/python3
# -*- coding:utf-8 -*-

from sqlalchemy.orm import Mapped, mapped_column

from app import db
from app.auth.password import hash_password, verify_login_password


class RbacUser(db.Model):
    __tablename__ = 'rbac_users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        db.String(64), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    role: Mapped[str] = mapped_column(db.String(20), nullable=False, default='viewer')
    is_active: Mapped[int] = mapped_column(db.SMALLINT, nullable=False, default=1)
    must_reset_password: Mapped[int] = mapped_column(
        db.SMALLINT, nullable=False, default=0
    )
    status_reason: Mapped[str] = mapped_column(
        db.String(500), nullable=False, default=''
    )
    create_time: Mapped[str] = mapped_column(db.String(25), nullable=False, default='')

    def set_password(self, plain):
        self.password_hash = hash_password(plain)

    def check_password(self, plain):
        return verify_login_password(plain, self.password_hash)
