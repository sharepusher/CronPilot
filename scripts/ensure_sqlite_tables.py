#!/usr/bin/env python
# -*- coding: utf-8
"""确保 SQLite 业务表存在（cron_infos / job_log / job_log_items）。"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, db  # noqa: E402
from datas.model.cron_infos import CronInfos  # noqa: F401,E402
from datas.model.job_log import JobLog  # noqa: F401,E402
from datas.model.job_log_items import JobLogItems  # noqa: F401,E402


def main():
    config_name = os.getenv('FLASK_CONFIG') or 'development'
    app = create_app(config_name)
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not uri.startswith('sqlite'):
        print('SKIP: 非 SQLite 业务库，不自动建表')
        return 0
    with app.app_context():
        db.create_all()
    print('OK: SQLite 业务表已就绪 ->', uri)
    return 0


if __name__ == '__main__':
    sys.exit(main())
