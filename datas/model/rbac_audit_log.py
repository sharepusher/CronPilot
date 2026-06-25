#!/usr/bin/python3
# -*- coding:utf-8 -*-

from app import db


class RbacAuditLog(db.Model):
    __tablename__ = 'rbac_audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(64), nullable=False, default='')
    action = db.Column(db.String(64), nullable=False, default='')
    resource = db.Column(db.String(128), nullable=False, default='')
    ip = db.Column(db.String(64), nullable=False, default='')
    status = db.Column(db.String(16), nullable=False, default='allow')
    create_time = db.Column(db.String(25), nullable=False, default='')
