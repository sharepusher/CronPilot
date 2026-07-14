#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""管理端业务变更审计（OPT-P1-09）。与 rbac_audit_logs 分表。"""

from app import db


class OperationLog(db.Model):
    __tablename__ = 'operation_log'
    id = db.Column(db.Integer, primary_key=True)
    create_time = db.Column(db.String(25), nullable=False, default='', index=True)
    action = db.Column(db.String(32), nullable=False, default='')
    channel = db.Column(db.String(8), nullable=False, default='')
    operator_type = db.Column(db.String(16), nullable=False, default='')
    operator_id = db.Column(db.String(64), nullable=False, default='', index=True)
    operator_name = db.Column(db.String(120), nullable=False, default='', index=True)
    operator_roles_json = db.Column(db.TEXT, nullable=False, default='')
    operator_permissions_json = db.Column(db.TEXT, nullable=False, default='')
    client_ip = db.Column(db.String(45), nullable=False, default='')
    target_type = db.Column(db.String(16), nullable=False, default='cron')
    target_id = db.Column(db.Integer, nullable=True)
    task_name = db.Column(db.String(120), nullable=False, default='', index=True)
    detail_json = db.Column(db.TEXT, nullable=False, default='')
    result = db.Column(db.String(8), nullable=False, default='ok')
    error_msg = db.Column(db.String(255), nullable=False, default='')
