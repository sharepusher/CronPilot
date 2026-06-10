#!/usr/bin/python3
# -*- coding:utf-8 -*-
# 已弃用：请使用 gun.py（:5860）。保留本文件仅为兼容旧 Supervisor 配置。
import gevent.monkey
gevent.monkey.patch_all()
bind = '0.0.0.0:5860'
workers = 2
worker_class = 'gevent'
x_forwarded_for_header = 'X-FORWARDED-FOR'
