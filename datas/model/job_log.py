#!/usr/bin/python3
# -*- coding:utf-8 -*-
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app import db
from datas.utils.id_generator import next_id


class JobLog(db.Model):
    __tablename__ = 'job_log'
    id: Mapped[int] = mapped_column(db.BigInteger, primary_key=True, default=next_id)
    trace_id: Mapped[str] = mapped_column(
        'trace_id',
        db.String(65),
        nullable=False,
        unique=True,
        server_default='',
        default='',
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
    create_time: Mapped[int] = mapped_column(db.BigInteger, nullable=False, default=0, index=True)
    take_time: Mapped[Optional[str]] = mapped_column(
        db.String(25), default='', doc='耗时时间'
    )
    started_at: Mapped[Optional[int]] = mapped_column(
        db.BigInteger, nullable=True, doc='HTTP 请求发出时间'
    )
    finished_at: Mapped[Optional[int]] = mapped_column(
        db.BigInteger, nullable=True, doc='执行终态时间（success/fail/timeout/error）'
    )
    timeout_sec: Mapped[Optional[int]] = mapped_column(
        db.Integer, nullable=True, doc='本次执行的超时阈值（秒）；NULL 表示使用系统默认'
    )
    trigger_source: Mapped[Optional[str]] = mapped_column(
        db.String(16), nullable=True, doc='触发来源: schedule | manual | one_shot'
    )
    actual_url: Mapped[Optional[str]] = mapped_column(
        db.TEXT, nullable=True, doc='实际发出的完整 URL（含注入的 trace_id/sign 参数）'
    )
    resolved_ip: Mapped[Optional[str]] = mapped_column(
        db.String(45), nullable=True, doc='DNS pinning 解析到的 IP 地址'
    )
    trigger_delay_ms: Mapped[Optional[int]] = mapped_column(
        db.Integer, nullable=True, doc='调度启动开销（毫秒）：@single_task 装饰器入口到 cron_do 函数体 t0 的时间差，通常 0-2ms；非 APScheduler 调度抖动'
    )

    def to_json(self):
        return {
            'id': self.id,
            'content': self.content,
            'status': self.status,
            'create_time': self.create_time,
        }
