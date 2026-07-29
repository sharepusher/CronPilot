#!/usr/bin/python3
# -*- coding:utf-8 -*-

from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class CronInfos(db.Model):
    __tablename__ = 'cron_infos'
    id: Mapped[int] = mapped_column(primary_key=True)
    task_name: Mapped[str] = mapped_column(db.String(120), nullable=False)
    task_keyword: Mapped[str] = mapped_column(
        db.String(500), nullable=False, default=''
    )
    run_date: Mapped[Optional[str]] = mapped_column(
        db.String(25), default='', doc='执行时间'
    )
    day_of_week: Mapped[Optional[str]] = mapped_column(
        db.String(10), default='', doc='星期几'
    )
    day: Mapped[Optional[str]] = mapped_column(db.String(20), default='', doc='号(日)')
    hour: Mapped[Optional[str]] = mapped_column(db.String(10), default='', doc='小时')
    minute: Mapped[Optional[str]] = mapped_column(db.String(10), default='', doc='分钟')
    second: Mapped[Optional[str]] = mapped_column(db.String(10), default='', doc='秒')
    req_url: Mapped[Optional[str]] = mapped_column(db.String(200), default='')
    req_method: Mapped[Optional[str]] = mapped_column(
        db.String(10), default='GET', doc='触发请求方式: GET/POST'
    )
    req_body: Mapped[Optional[str]] = mapped_column(
        db.TEXT, default='', doc='POST 时的 JSON body'
    )
    status: Mapped[Optional[int]] = mapped_column(
        db.SMALLINT, default=True, doc='运行状态，0停止1运行中-1结束任务'
    )
    created_at: Mapped[Optional[str]] = mapped_column(
        db.String(25), default='', doc='创建时间'
    )
    updated_at: Mapped[Optional[str]] = mapped_column(
        db.String(25), default='', doc='最后配置编辑时间'
    )
    retire_reason: Mapped[Optional[str]] = mapped_column(
        db.String(500), default='', doc='下线原因'
    )
    retired_at: Mapped[Optional[str]] = mapped_column(
        db.String(25), default='', doc='下线时刻'
    )
    scope_type: Mapped[str] = mapped_column(
        db.String(16),
        nullable=False,
        default='GLOBAL',
        server_default='GLOBAL',
        doc='GLOBAL=全局共享；GROUP=业务组隔离',
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        db.Integer,
        nullable=True,
        default=None,
        doc='scope_type=GROUP 时所属 resource_groups.id；GLOBAL 时为 NULL',
    )
    last_operator_name: Mapped[str] = mapped_column(
        db.String(120),
        nullable=False,
        default='',
        doc='最近发布/编辑/下线操作人展示名',
    )
    last_operated_at: Mapped[str] = mapped_column(
        db.String(25),
        nullable=False,
        default='',
        doc='最近发布/编辑/下线时间',
    )
    timeout_sec: Mapped[Optional[int]] = mapped_column(
        db.Integer,
        nullable=True,
        default=None,
        doc='单任务 HTTP 超时（秒）；NULL = 系统默认 5s；有效范围 1–120',
    )
