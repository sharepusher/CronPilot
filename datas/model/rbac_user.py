#!/usr/bin/python3
# -*- coding:utf-8 -*-

from app import db
from app.auth.password import hash_password, verify_login_password


class RbacUser(db.Model):
    __tablename__ = 'rbac_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')
    is_active = db.Column(db.SMALLINT, nullable=False, default=1)
    must_reset_password = db.Column(db.SMALLINT, nullable=False, default=0)
    status_reason = db.Column(db.String(500), nullable=False, default='')
    create_time = db.Column(db.String(25), nullable=False, default='')

    def set_password(self, plain):
        self.password_hash = hash_password(plain)

    def check_password(self, plain):
        return verify_login_password(plain, self.password_hash)
