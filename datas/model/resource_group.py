#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""业务资源组（OPT-P2-12 Resource Scope）。与 RBAC 角色解耦。"""

from app import db


class ResourceGroup(db.Model):
    __tablename__ = 'resource_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, default='')
    code = db.Column(db.String(64), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=False, default='')
    create_time = db.Column(db.String(25), nullable=False, default='')
