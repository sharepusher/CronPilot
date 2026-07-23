#!/usr/bin/python3
# -*- coding:utf-8 -*-
import os
import gevent.monkey
gevent.monkey.patch_all()
bind = '0.0.0.0:5860'
workers=2
worker_class='gevent'
x_forwarded_for_header = 'X-FORWARDED-FOR'
logger_class = 'app.gunicorn_logger.CronPilotLogger'

# Prometheus multiprocess aggregation — each worker writes to its own .db file
_prom_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datas', 'prometheus_tmp')
os.makedirs(_prom_dir, exist_ok=True)
os.environ.setdefault('PROMETHEUS_MULTIPROC_DIR', _prom_dir)
