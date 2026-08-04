#!/usr/bin/env python
# -*- coding: utf-8
"""确保业务库表存在：SQLite / MySQL（cron_infos、组表、RBAC、补列）。

部署入口：scripts/ensure_business_tables.sh
（旧名 ensure_sqlite_tables.* 仍转发到本脚本。）
- create_all：仅创建缺失表，不删不改已有表结构
- 补列：对已有 cron_infos / job_log 按需 ALTER ADD COLUMN
- 非 sqlite/mysql URI：SKIP
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, db  # noqa: E402
from datas.model.cron_infos import CronInfos  # noqa: F401,E402
from datas.model.job_log import JobLog  # noqa: F401,E402
from datas.model.job_log_items import JobLogItems  # noqa: F401,E402
from datas.model.job_health import JobHealth  # noqa: F401,E402
from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401,E402
from datas.model.rbac_user import RbacUser  # noqa: F401,E402
from datas.model.operation_log import OperationLog  # noqa: F401,E402
from datas.model.resource_group import ResourceGroup  # noqa: F401,E402
from datas.model.user_group import UserGroup  # noqa: F401,E402
from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401,E402


def business_db_backend(uri):
    """返回 sqlite / mysql / 其它。供单测与 main 门禁复用。"""
    if not uri:
        return ''
    u = uri.strip().lower()
    if u.startswith('sqlite'):
        return 'sqlite'
    if u.startswith('mysql'):
        return 'mysql'
    return ''


def main():
    config_name = os.getenv('FLASK_CONFIG') or 'development'
    app = create_app(config_name)
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
    backend = business_db_backend(uri)
    if not backend:
        print('SKIP: 业务库非 SQLite/MySQL，不自动建表 ->', uri)
        return 0
    with app.app_context():
        db.create_all()
        _ensure_job_log_columns()
        _ensure_cron_infos_columns(backend=backend)
        _ensure_rbac_users_columns()
        _ensure_rbac_registration_requests_columns()
        _ensure_rbac_audit_logs_columns()
        _ensure_time_column_indexes()
        from app.rbac.services import ensure_seed_admin, ensure_existing_users_have_token, expire_stale_registrations
        ensure_seed_admin()
        ensure_existing_users_have_token()
        expire_stale_registrations()
        # 关键表存在断言（防止启动时表缺失导致全站 500）
        from sqlalchemy import inspect as sa_inspect
        critical_tables = [
            'cron_infos', 'job_log', 'resource_groups',
            'rbac_users', 'rbac_audit_logs',
        ]
        insp = sa_inspect(db.engine)
        missing = [t for t in critical_tables if not insp.has_table(t)]
        if missing:
            print('FATAL: 关键表缺失 ->', ', '.join(missing))
            return 1
    print('OK: %s 业务表已就绪 ->' % backend, uri)
    return 0


def _ensure_job_log_columns():
    """已有库补列（create_all 不会 ALTER）。SQLite / MySQL 通用 DDL。"""
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
    if 'started_at' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN started_at VARCHAR(25)")
    if 'finished_at' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN finished_at VARCHAR(25)")
    if 'timeout_sec' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN timeout_sec INTEGER")
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    print('OK: job_log 列已补全 ->', ', '.join(
        c.split()[-1] for c in alters
    ))


def _ensure_cron_infos_columns(backend=''):
    """LIFECYCLE-2 + Scope + POST 触发请求：已有库补列。"""
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
    if 'scope_type' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN scope_type VARCHAR(16) DEFAULT 'GLOBAL'")
    if 'group_id' not in cols:
        alters.append('ALTER TABLE cron_infos ADD COLUMN group_id INTEGER')
    if 'req_method' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN req_method VARCHAR(10) DEFAULT 'GET'")
    if 'req_body' not in cols:
        if backend == 'mysql':
            # MySQL 5.7 不支持 TEXT/BLOB DEFAULT，避免升级补列失败。
            alters.append("ALTER TABLE cron_infos ADD COLUMN req_body TEXT")
        else:
            alters.append("ALTER TABLE cron_infos ADD COLUMN req_body TEXT DEFAULT ''")
    if 'last_operator_name' not in cols:
        alters.append(
            "ALTER TABLE cron_infos ADD COLUMN last_operator_name VARCHAR(120) DEFAULT ''"
        )
    if 'last_operated_at' not in cols:
        alters.append(
            "ALTER TABLE cron_infos ADD COLUMN last_operated_at VARCHAR(25) DEFAULT ''"
        )
    if 'timeout_sec' not in cols:
        alters.append('ALTER TABLE cron_infos ADD COLUMN timeout_sec INTEGER')
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    print('OK: cron_infos 列已补全 ->', ', '.join(a.split()[5] for a in alters))


def _ensure_rbac_users_columns():
    """强制改密 / 启停缘由：已有库补列。现有用户默认 must_reset_password=0。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('rbac_users'):
        return
    cols = {c['name'] for c in insp.get_columns('rbac_users')}
    alters = []
    if 'must_reset_password' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN must_reset_password '
            'SMALLINT NOT NULL DEFAULT 0'
        )
    if 'status_reason' not in cols:
        alters.append(
            "ALTER TABLE rbac_users ADD COLUMN status_reason "
            "VARCHAR(500) NOT NULL DEFAULT ''"
        )
    if 'api_token' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN api_token VARCHAR(64)'
        )
    if 'api_token_expires_at' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN api_token_expires_at VARCHAR(25)'
        )
    if 'email' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN email VARCHAR(128)'
        )
    if 'job_title' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN job_title VARCHAR(64)'
        )
    if 'nickname' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN nickname VARCHAR(64)'
        )
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    print('OK: rbac_users 列已补全 ->', ', '.join(a.split()[5] for a in alters))


def _ensure_rbac_registration_requests_columns():
    """注册申请表补列（OPT-P1-10：job_title / nickname）。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('rbac_registration_requests'):
        return
    cols = {c['name'] for c in insp.get_columns('rbac_registration_requests')}
    alters = []
    if 'job_title' not in cols:
        alters.append(
            "ALTER TABLE rbac_registration_requests ADD COLUMN job_title "
            "VARCHAR(64) NOT NULL DEFAULT ''"
        )
    if 'nickname' not in cols:
        alters.append(
            "ALTER TABLE rbac_registration_requests ADD COLUMN nickname "
            "VARCHAR(64) NOT NULL DEFAULT ''"
        )
    need_backfill_pending = 'pending_username' not in cols
    if need_backfill_pending:
        alters.append(
            'ALTER TABLE rbac_registration_requests ADD COLUMN pending_username '
            'VARCHAR(64)'
        )
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
        # 回填：已有 pending 记录需设置 pending_username
        if need_backfill_pending:
            conn.execute(text(
                "UPDATE rbac_registration_requests "
                "SET pending_username = username "
                "WHERE status = 'pending'"
            ))
            # 添加唯一索引（分步执行，兼容 SQLite）
            try:
                conn.execute(text(
                    'CREATE UNIQUE INDEX uix_reg_pending_username '
                    'ON rbac_registration_requests(pending_username)'
                ))
            except Exception:
                pass  # 索引已存在（idempotent）
    print('OK: rbac_registration_requests 列已补全 ->',
          ', '.join(a.split()[5] for a in alters))


def _ensure_rbac_audit_logs_columns():
    """审计日志 Scope 过滤（OPT-P2-13）：已有库补列。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('rbac_audit_logs'):
        return
    cols = {c['name'] for c in insp.get_columns('rbac_audit_logs')}
    alters = []
    if 'actor_group_ids' not in cols:
        alters.append(
            "ALTER TABLE rbac_audit_logs ADD COLUMN actor_group_ids "
            "VARCHAR(255) NOT NULL DEFAULT ''"
        )
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    print('OK: rbac_audit_logs 列已补全 ->', ', '.join(a.split()[5] for a in alters))


def _ensure_time_column_indexes():
    """为所有表的 create_time / update_time 类字段补建索引（幂等）。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    index_targets = [
        ('rbac_audit_logs', 'create_time'),
        ('rbac_users', 'create_time'),
        ('resource_groups', 'create_time'),
        ('cron_infos', 'created_at'),
        ('cron_infos', 'updated_at'),
        ('job_log', 'create_time'),
        ('job_health', 'updated_at'),
    ]
    created = []
    for table, col in index_targets:
        if not insp.has_table(table):
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if col not in cols:
            continue
        idx_name = 'ix_%s_%s' % (table, col)
        existing = {idx['name'] for idx in insp.get_indexes(table)}
        if idx_name in existing:
            continue
        try:
            db.session.execute(
                text('CREATE INDEX %s ON %s (%s)' % (idx_name, table, col))
            )
            db.session.commit()
            created.append('%s.%s' % (table, col))
        except Exception:
            db.session.rollback()
    if created:
        print('OK: 时间列索引已创建 ->', ', '.join(created))


def _ensure_job_log_http_status_column():
    _ensure_job_log_columns()


if __name__ == '__main__':
    sys.exit(main())
