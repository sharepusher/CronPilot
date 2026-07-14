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
from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401,E402
from datas.model.rbac_user import RbacUser  # noqa: F401,E402
from datas.model.operation_log import OperationLog  # noqa: F401,E402


def main():
    config_name = os.getenv('FLASK_CONFIG') or 'development'
    app = create_app(config_name)
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not uri.startswith('sqlite'):
        print('SKIP: 非 SQLite 业务库，不自动建表')
        return 0
    with app.app_context():
        db.create_all()
        _ensure_job_log_columns()
        _ensure_cron_infos_columns()
        from app.rbac.services import ensure_seed_admin
        ensure_seed_admin()
    print('OK: SQLite 业务表已就绪 ->', uri)
    return 0


def _ensure_job_log_columns():
    """已有 SQLite 库补列（create_all 不会 ALTER）。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('job_log'):
        return
    cols = {c['name'] for c in insp.get_columns('job_log')}
    alters = []
    if 'http_status' not in cols:
        alters.append('ALTER TABLE job_log ADD COLUMN http_status INTEGER')
    if 'status' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN status VARCHAR(16)")
    if 'fail_reason' not in cols:
        alters.append('ALTER TABLE job_log ADD COLUMN fail_reason VARCHAR(128)')
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    print('OK: job_log 列已补全 ->', ', '.join(
        c.split()[-1] for c in alters
    ))


def _ensure_cron_infos_columns():
    """LIFECYCLE-2：已有 SQLite 库补 created_at/updated_at/retire_*。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('cron_infos'):
        return
    cols = {c['name'] for c in insp.get_columns('cron_infos')}
    alters = []
    if 'created_at' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN created_at VARCHAR(25) DEFAULT ''")
    if 'updated_at' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN updated_at VARCHAR(25) DEFAULT ''")
    if 'retire_reason' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN retire_reason VARCHAR(500) DEFAULT ''")
    if 'retired_at' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN retired_at VARCHAR(25) DEFAULT ''")
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    print('OK: cron_infos 列已补全 ->', ', '.join(a.split()[5] for a in alters))


def _ensure_job_log_http_status_column():
    _ensure_job_log_columns()


if __name__ == '__main__':
    sys.exit(main())
