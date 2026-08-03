#!/usr/bin/python3
# -*- coding:utf-8 -*-
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app import db


class JobLog(db.Model):
    __tablename__ = 'job_log'
    id: Mapped[int] = mapped_column(primary_key=True)
    log_id: Mapped[str] = mapped_column(
        db.String(65),
        nullable=False,
        index=True,
        server_default='',
        default='log id 用uuid生成唯一id,用来用户更新',
    )
    cron_info_id: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=0, index=True
    )
    content: Mapped[str] = mapped_column(
        db.TEXT, nullable=False, default='', doc='返回的内容'
    )
    http_status: Mapped[Optional[int]] = mapped_column(
        db.Integer, nullable=True, doc='HTTP 响应状态码；未发起请求或异常时为 NULL'
    )
    status: Mapped[Optional[str]] = mapped_column(
        db.String(16), nullable=True, doc='pending | running | success | fail | timeout | error'
    )
    fail_reason: Mapped[Optional[str]] = mapped_column(
        db.String(128), nullable=True, doc='失败原因短标签'
    )
    create_time: Mapped[str] = mapped_column(db.String(25), nullable=False, default='', index=True)
    take_time: Mapped[Optional[str]] = mapped_column(
        db.String(25), default='', doc='耗时时间'
    )
    started_at: Mapped[Optional[str]] = mapped_column(
        db.String(25), nullable=True, doc='HTTP 请求发出时间'
    )
    finished_at: Mapped[Optional[str]] = mapped_column(
        db.String(25), nullable=True, doc='执行终态时间（success/fail/timeout/error）'
    )
    timeout_sec: Mapped[Optional[int]] = mapped_column(
        db.Integer, nullable=True, doc='本次执行的超时阈值（秒）；NULL 表示使用系统默认'
    )

    def to_json(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'remark': self.remark,
            'content': self.content,
            'traces': self.traces,
            'status': self.status,
            'create_time': self.create_time,
        }
