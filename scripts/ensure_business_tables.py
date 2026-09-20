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
import uuid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, db  # noqa: E402
from datas.model.cron_infos import CronInfos  # noqa: F401,E402
from datas.model.job_health import JobHealth  # noqa: F401,E402
from datas.model.job_log import JobLog  # noqa: F401,E402
from datas.model.job_log_event import JobLogEvent  # noqa: F401,E402
from datas.model.job_log_items import JobLogItems  # noqa: F401,E402
from datas.model.operation_log import OperationLog  # noqa: F401,E402
from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401,E402
from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401,E402
from datas.model.rbac_user import RbacUser  # noqa: F401,E402
from datas.model.resource_group import ResourceGroup  # noqa: F401,E402
from datas.model.tag import Tag  # noqa: F401,E402
from datas.model.task_group import TaskGroup  # noqa: F401,E402
from datas.model.task_tag import TaskTag  # noqa: F401,E402
from datas.model.user_group import UserGroup  # noqa: F401,E402


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
        if backend == 'sqlite':
            _ensure_sqlite_event_id_autoincrement()
        _ensure_job_log_columns()
        _backfill_job_log_execution_semantics()
        _ensure_job_log_event_columns()
        _backfill_job_log_event_run_ids()
        _rename_log_id_to_trace_id(backend=backend)
        _ensure_job_log_trace_ids(backend=backend)
        _ensure_job_log_item_columns()
        _ensure_cron_infos_columns(backend=backend)
        _ensure_rbac_users_columns()
        _ensure_rbac_registration_requests_columns()
        _ensure_rbac_audit_logs_columns()
        _ensure_time_column_indexes()
        _ensure_composite_indexes()
        _migrate_group_id_to_task_groups()
        _ensure_tags_group_id_column()
        _migrate_tags_group_isolation()
        _ensure_tags_description_column()
        _drop_resource_groups_code_column(backend=backend)
        _migrate_time_columns_to_bigint()
        _cleanup_orphan_health_records()
        _correct_subthreshold_health_ok()
        _ensure_id_columns_bigint(backend=backend)
        from app.rbac.services import (
            ensure_existing_users_have_token,
            ensure_seed_admin,
            expire_stale_registrations,
        )
        ensure_seed_admin()
        ensure_existing_users_have_token()
        expire_stale_registrations()
        _bump_auth_version_once()
        # 关键表存在断言（防止启动时表缺失导致全站 500）
        from sqlalchemy import inspect as sa_inspect
        critical_tables = [
            'cron_infos', 'job_log', 'resource_groups',
            'rbac_users', 'rbac_audit_logs',
            'task_groups', 'tags', 'task_tags',
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
        alters.append("ALTER TABLE job_log ADD COLUMN started_at BIGINT")
    if 'finished_at' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN finished_at BIGINT")
    if 'timeout_sec' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN timeout_sec INTEGER")
    if 'trigger_source' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN trigger_source VARCHAR(16)")
    if 'actual_url' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN actual_url TEXT")
    if 'resolved_ip' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN resolved_ip VARCHAR(45)")
    if 'trigger_delay_ms' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN trigger_delay_ms INTEGER")
    if 'observability_state' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN observability_state VARCHAR(16)")
    if 'observability_drop_reason' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN observability_drop_reason VARCHAR(32)")
    if 'failure_stage' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN failure_stage VARCHAR(24)")
    if 'transport_state' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN transport_state VARCHAR(32)")
    if 'response_received' not in cols:
        alters.append("ALTER TABLE job_log ADD COLUMN response_received BOOLEAN")
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    print('OK: job_log 列已补全 ->', ', '.join(
        c.split()[-1] for c in alters
    ))


def _backfill_job_log_execution_semantics():
    """为历史执行记录补齐可解释的请求/响应状态，不猜测远端已收到请求。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('job_log'):
        return
    cols = {c['name'] for c in insp.get_columns('job_log')}
    required = {'http_status', 'status', 'fail_reason', 'actual_url', 'content',
                'failure_stage', 'transport_state', 'response_received'}
    if not required.issubset(cols):
        return
    with db.engine.begin() as conn:
        conn.execute(text(
            "UPDATE job_log SET failure_stage = 'remote_response', "
            "transport_state = 'response_received', response_received = 1 "
            "WHERE http_status IS NOT NULL AND (failure_stage IS NULL OR response_received IS NULL)"
        ))
        conn.execute(text(
            "UPDATE job_log SET failure_stage = CASE "
            "WHEN actual_url IS NULL OR actual_url = '' THEN 'pre_request' ELSE 'transport' END, "
            "transport_state = CASE "
            "WHEN actual_url IS NULL OR actual_url = '' THEN 'not_started' ELSE 'failed_before_response' END, "
            "response_received = 0 "
            "WHERE http_status IS NULL AND status IN ('error', 'fail', 'timeout') "
            "AND (failure_stage IS NULL OR response_received IS NULL)"
        ))
        result = conn.execute(text(
            "UPDATE job_log SET fail_reason = 'client_incompatible' "
            "WHERE fail_reason = 'internal' AND content LIKE '%assert_hostname%'"
        ))
    if result.rowcount:
        print('OK: 历史 HTTP 客户端兼容性错误已归类 ->', result.rowcount)


def _ensure_job_log_event_columns():
    """补齐旧 job_log_events 的执行实例关联字段。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('job_log_events'):
        return
    cols = {c['name'] for c in insp.get_columns('job_log_events')}
    alters = []
    if 'run_id' not in cols:
        alters.append('ALTER TABLE job_log_events ADD COLUMN run_id BIGINT')
    if 'schema_version' not in cols:
        alters.append('ALTER TABLE job_log_events ADD COLUMN schema_version SMALLINT DEFAULT 1')
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    print('OK: job_log_events 列已补全 ->', ', '.join(c.split()[-1] for c in alters))


def _ensure_sqlite_event_id_autoincrement():
    """Make the existing event PK a SQLite rowid alias without changing rows.

    SQLite only auto-allocates a primary key when the declared type is exactly
    INTEGER.  Older databases created ``job_log_events.id`` as BIGINT, so an
    omitted id would otherwise fail with NOT NULL.  The rebuild is strictly a
    schema operation: every existing column value is copied unchanged, and the
    operation is transactional.
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('job_log_events'):
        return
    id_column = next(
        (col for col in insp.get_columns('job_log_events') if col['name'] == 'id'),
        None,
    )
    if id_column is None or str(id_column['type']).upper() == 'INTEGER':
        return

    def quote(name):
        return '"%s"' % str(name).replace('"', '""')

    columns = db.session.execute(text('PRAGMA table_info("job_log_events")')).fetchall()
    if not columns:
        return
    temp_table = 'job_log_events__id_switch_old'
    if insp.has_table(temp_table):
        raise RuntimeError('job_log_events ID switch left an unfinished temporary table')

    unique_constraints = insp.get_unique_constraints('job_log_events')
    indexes = insp.get_indexes('job_log_events')
    names = [column[1] for column in columns]
    definitions = []
    for _cid, name, col_type, not_null, default, pk in columns:
        if name == 'id':
            definitions.append('%s INTEGER PRIMARY KEY' % quote(name))
            continue
        definition = '%s %s' % (quote(name), col_type or 'BLOB')
        if not_null:
            definition += ' NOT NULL'
        if default is not None:
            definition += ' DEFAULT %s' % default
        definitions.append(definition)
    for constraint in unique_constraints:
        constraint_name = constraint.get('name')
        constraint_columns = constraint.get('column_names') or []
        if constraint_columns:
            prefix = 'CONSTRAINT %s ' % quote(constraint_name) if constraint_name else ''
            definitions.append(
                '%sUNIQUE (%s)' % (
                    prefix,
                    ', '.join(quote(name) for name in constraint_columns),
                )
            )

    with db.engine.begin() as conn:
        conn.exec_driver_sql(
            'ALTER TABLE job_log_events RENAME TO %s' % quote(temp_table)
        )
        conn.exec_driver_sql(
            'CREATE TABLE job_log_events (%s)' % ', '.join(definitions)
        )
        quoted_names = ', '.join(quote(name) for name in names)
        conn.exec_driver_sql(
            'INSERT INTO job_log_events (%s) SELECT %s FROM %s' % (
                quoted_names,
                quoted_names,
                quote(temp_table),
            )
        )
        # The old table keeps its index names after the rename; drop it before
        # recreating those indexes on the new table.  The surrounding
        # transaction restores the old table if any later DDL fails.
        conn.exec_driver_sql('DROP TABLE %s' % quote(temp_table))
        for index in indexes:
            index_name = index.get('name')
            index_columns = index.get('column_names') or []
            if not index_name or not index_columns:
                continue
            unique = 'UNIQUE ' if index.get('unique') else ''
            conn.exec_driver_sql(
                'CREATE %sINDEX %s ON job_log_events (%s)' % (
                    unique,
                    quote(index_name),
                    ', '.join(quote(name) for name in index_columns),
                )
            )
    print('OK: SQLite job_log_events.id 已切换为 INTEGER PRIMARY KEY（历史行值不变）')


def _backfill_job_log_event_run_ids():
    """Backfill only unambiguous legacy events; never guess a parent run."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('job_log_events') or not insp.has_table('job_log'):
        return
    event_cols = {c['name'] for c in insp.get_columns('job_log_events')}
    if 'run_id' not in event_cols:
        return
    with db.engine.begin() as conn:
        events = conn.execute(text(
            'SELECT id, trace_id FROM job_log_events WHERE run_id IS NULL'
        )).fetchall()
        matched = 0
        for event_id, trace_id in events:
            parents = conn.execute(text(
                'SELECT id FROM job_log WHERE trace_id = :trace_id'
            ), {'trace_id': trace_id}).fetchall()
            if len(parents) != 1:
                continue
            conn.execute(text(
                'UPDATE job_log_events SET run_id = :run_id WHERE id = :id'
            ), {'run_id': parents[0][0], 'id': event_id})
            matched += 1
    if matched:
        print('OK: job_log_events.run_id 已回填 ->', matched)


def _ensure_job_log_item_columns():
    """为既有业务回传日志补充稳定排序时间。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('job_log_items'):
        return
    cols = {c['name'] for c in insp.get_columns('job_log_items')}
    if 'occurred_at_ms' not in cols:
        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE job_log_items ADD COLUMN occurred_at_ms BIGINT'))


def _ensure_job_log_trace_ids(backend=''):
    """Backfill legacy blank/duplicate trace IDs before adding the unique index."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('job_log'):
        return
    if 'trace_id' not in {c['name'] for c in insp.get_columns('job_log')}:
        raise RuntimeError('job_log lacks trace_id after legacy column migration')
    # Complete the data repair before DDL.  Keeping the unique-index creation
    # in a separate transaction is required by SQLite's schema visibility
    # rules and is equally safe for MySQL.
    with db.engine.begin() as conn:
        rows = conn.execute(text('SELECT id, trace_id FROM job_log ORDER BY id')).fetchall()
        parent_counts = {}
        for row in rows:
            normalized = (row[1] or '').strip()
            parent_counts[normalized] = parent_counts.get(normalized, 0) + 1

        # A duplicate parent trace ID cannot be safely remapped when dependent
        # rows already use that value: their original parent is unknowable.
        # Fail closed before changing any parent row instead of silently
        # orphaning or misattributing execution evidence.
        dependent_tables = ('job_log_items', 'job_log_events')
        for trace_id, parent_count in parent_counts.items():
            if parent_count < 2:
                continue
            for table in dependent_tables:
                if not insp.has_table(table):
                    continue
                dependent_cols = {c['name'] for c in insp.get_columns(table)}
                if 'trace_id' not in dependent_cols:
                    continue
                if trace_id:
                    dependent_count = conn.execute(text(
                        'SELECT COUNT(*) FROM {} WHERE trace_id = :trace_id'.format(table)
                    ), {'trace_id': trace_id}).scalar_one()
                else:
                    dependent_count = conn.execute(text(
                        'SELECT COUNT(*) FROM {} WHERE trace_id IS NULL OR trace_id = :trace_id'.format(table)
                    ), {'trace_id': ''}).scalar_one()
                if dependent_count:
                    raise RuntimeError(
                        'ambiguous trace_id {} has {} dependent rows in {}'.format(
                            trace_id or '<blank>', dependent_count, table,
                        )
                    )

        seen = set()
        for row in rows:
            trace_id = (row[1] or '').strip()
            if not trace_id or trace_id in seen:
                trace_id = str(uuid.uuid1())
                while trace_id in seen:
                    trace_id = str(uuid.uuid1())
                conn.execute(
                    text('UPDATE job_log SET trace_id = :trace_id WHERE id = :id'),
                    {'trace_id': trace_id, 'id': row[0]},
                )
            seen.add(trace_id)

    insp = inspect(db.engine)
    indexes = {index['name'] for index in insp.get_indexes('job_log')}
    unique_columns = {
        tuple(constraint.get('column_names') or [])
        for constraint in insp.get_unique_constraints('job_log')
    }
    if 'uq_job_log_trace_id' in indexes or ('trace_id',) in unique_columns:
        return

    with db.engine.begin() as conn:
        duplicate_count = conn.execute(text(
            'SELECT COUNT(*) FROM ('
            'SELECT trace_id FROM job_log GROUP BY trace_id HAVING COUNT(*) > 1'
            ') AS duplicate_trace_ids'
        )).scalar_one()
        if duplicate_count:
            raise RuntimeError('job_log trace_id backfill left duplicate values')
        conn.execute(text('CREATE UNIQUE INDEX uq_job_log_trace_id ON job_log (trace_id)'))


def _ensure_cron_infos_columns(backend=''):
    """LIFECYCLE-2 + Scope + POST 触发请求：已有库补列。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('cron_infos'):
        return
    cols = {c['name'] for c in insp.get_columns('cron_infos')}
    alters = []
    if 'created_at' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN created_at BIGINT DEFAULT 0")
    if 'updated_at' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN updated_at BIGINT DEFAULT 0")
    if 'retire_reason' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN retire_reason VARCHAR(500) DEFAULT ''")
    if 'retired_at' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN retired_at BIGINT DEFAULT 0")
    if 'scope_type' not in cols:
        alters.append("ALTER TABLE cron_infos ADD COLUMN scope_type VARCHAR(16) DEFAULT 'GLOBAL'")
    # group_id 已迁移至 task_groups 表（OPT-P1-11），不再补列
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
            "ALTER TABLE cron_infos ADD COLUMN last_operated_at BIGINT DEFAULT 0"
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
    """强制改密 / 启停缘由 / 会话版本：为已有用户表补列。"""
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
    if 'auth_version' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN auth_version '
            'INTEGER NOT NULL DEFAULT 0'
        )
    if 'api_token' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN api_token VARCHAR(64)'
        )
    if 'api_token_expires_at' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN api_token_expires_at BIGINT'
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
    if 'last_login_at' not in cols:
        alters.append(
            'ALTER TABLE rbac_users ADD COLUMN last_login_at BIGINT'
        )
    if not alters:
        return
    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    print('OK: rbac_users 列已补全 ->', ', '.join(a.split()[5] for a in alters))


AUTH_VERSION_BUMP_FLAG = 'opt_p0_22_auth_version_bump'


def _bump_auth_version_once():
    """OPT-P0-22 §4.4：一次性将全部用户 auth_version +1，使既有 Web Session 失效。

    幂等：cp_schema_flags 表记录 flag；已执行则跳过。
    """
    from sqlalchemy import inspect, text

    from datas.utils.times import utc_now_hms

    insp = inspect(db.engine)
    if not insp.has_table('rbac_users'):
        return
    cols = {c['name'] for c in insp.get_columns('rbac_users')}
    if 'auth_version' not in cols:
        return
    with db.engine.begin() as conn:
        # SQLite 偶发 journal 锁：拉长等待，避免启动失败留下「有 flag 无 bump」
        try:
            conn.execute(text('PRAGMA busy_timeout=30000'))
        except Exception:
            pass
        conn.execute(text(
            'CREATE TABLE IF NOT EXISTS cp_schema_flags ('
            'flag_name VARCHAR(64) PRIMARY KEY, '
            'applied_at BIGINT NOT NULL DEFAULT 0)'
        ))
        row = conn.execute(
            text(
                'SELECT 1 FROM cp_schema_flags WHERE flag_name = :flag'
            ),
            {'flag': AUTH_VERSION_BUMP_FLAG},
        ).first()
        if row:
            return
        conn.execute(text(
            'UPDATE rbac_users SET auth_version = COALESCE(auth_version, 0) + 1'
        ))
        conn.execute(
            text(
                'INSERT INTO cp_schema_flags (flag_name, applied_at) '
                'VALUES (:flag, :ts)'
            ),
            {'flag': AUTH_VERSION_BUMP_FLAG, 'ts': utc_now_hms()},
        )
    print('OK: OPT-P0-22 auth_version 一次性 bump 已执行')


def _ensure_rbac_registration_requests_columns():
    """注册申请表补列（OPT-P1-10 + OPT-P0-22）。"""
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
    if 'is_reactivation' not in cols:
        alters.append(
            'ALTER TABLE rbac_registration_requests ADD COLUMN is_reactivation '
            'SMALLINT NOT NULL DEFAULT 0'
        )
    if 'target_user_id' not in cols:
        alters.append(
            'ALTER TABLE rbac_registration_requests ADD COLUMN target_user_id '
            'INTEGER'
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
    """审计日志 Scope 过滤（OPT-P2-13）+ OPT-P0-22 detail。"""
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
    if 'detail' not in cols:
        alters.append(
            'ALTER TABLE rbac_audit_logs ADD COLUMN detail TEXT'
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


def _ensure_composite_indexes():
    """补建复合索引（幂等）。

    job_log (cron_info_id, create_time) — 逾期检测和最近执行时间查询
    使用 Loose Index Scan 加速 MAX(create_time) GROUP BY cron_info_id。
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    composite_targets = [
        ('job_log', 'ix_job_log_cron_id_create_time', ['cron_info_id', 'create_time']),
        ('job_log_events', 'ix_job_log_events_run_id_seq', ['run_id', 'seq']),
    ]
    created = []
    for table, idx_name, columns in composite_targets:
        if not insp.has_table(table):
            continue
        existing_cols = {c['name'] for c in insp.get_columns(table)}
        if not all(c in existing_cols for c in columns):
            continue
        existing_indexes = {idx['name'] for idx in insp.get_indexes(table)}
        if idx_name in existing_indexes:
            continue
        col_list = ', '.join(columns)
        try:
            db.session.execute(
                text('CREATE INDEX %s ON %s (%s)' % (idx_name, table, col_list))
            )
            db.session.commit()
            created.append('%s(%s)' % (table, col_list))
        except Exception:
            db.session.rollback()
    if created:
        print('OK: 复合索引已创建 ->', ', '.join(created))


def _migrate_group_id_to_task_groups():
    """将 cron_infos.group_id 数据迁移到 task_groups 表，然后删除 group_id 列（幂等）。

    仅处理 scope_type='GROUP' 且 group_id IS NOT NULL 且尚未在 task_groups 中的记录。
    迁移完成后尝试删除 group_id 列（SQLite 3.35+ / MySQL 均支持）。
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('cron_infos') or not insp.has_table('task_groups'):
        return
    cols = {c['name'] for c in insp.get_columns('cron_infos')}
    if 'group_id' not in cols:
        return  # group_id 列已被删除，迁移已完成
    backend = business_db_backend(str(db.engine.url))
    if backend == 'mysql':
        insert_sql = (
            "INSERT IGNORE INTO task_groups (task_id, group_id) "
            "SELECT id, group_id FROM cron_infos "
            "WHERE scope_type = 'GROUP' AND group_id IS NOT NULL"
        )
    else:
        insert_sql = (
            "INSERT OR IGNORE INTO task_groups (task_id, group_id) "
            "SELECT id, group_id FROM cron_infos "
            "WHERE scope_type = 'GROUP' AND group_id IS NOT NULL"
        )
    with db.engine.begin() as conn:
        result = conn.execute(text(insert_sql))
        if result.rowcount:
            print('OK: group_id -> task_groups 迁移 ->', result.rowcount, '行')
    # 删除 group_id 列
    try:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE cron_infos DROP COLUMN group_id"))
        print('OK: cron_infos.group_id 列已删除')
    except Exception as e:
        print('WARN: 无法删除 group_id 列（可忽略）:', e)


def _ensure_tags_group_id_column():
    """tags 表补 group_id 列（标签业务组隔离 OPT-P1-11）。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('tags'):
        return
    cols = {c['name'] for c in insp.get_columns('tags')}
    if 'group_id' in cols:
        return
    with db.engine.begin() as conn:
        conn.execute(text('ALTER TABLE tags ADD COLUMN group_id INTEGER'))
    # 删除旧的 name 唯一索引（如有），改为 (name, group_id) 联合唯一
    backend = business_db_backend(str(db.engine.url))
    try:
        with db.engine.begin() as conn:
            if backend == 'mysql':
                conn.execute(text('ALTER TABLE tags DROP INDEX ix_tags_name'))
            else:
                conn.execute(text('DROP INDEX IF EXISTS ix_tags_name'))
    except Exception:
        pass
    try:
        with db.engine.begin() as conn:
            if backend == 'mysql':
                conn.execute(text(
                    'ALTER TABLE tags ADD UNIQUE INDEX uix_tag_name_group (name, group_id)'
                ))
            else:
                conn.execute(text(
                    'CREATE UNIQUE INDEX IF NOT EXISTS uix_tag_name_group '
                    'ON tags (name, group_id)'
                ))
    except Exception:
        pass  # 索引已存在（幂等）
    print('OK: tags 列已补全 -> group_id')


def _migrate_tags_group_isolation():
    """按任务组推断标签归属（标签业务组隔离 OPT-P1-11）。

    迁移策略：
    - 对每个 group_id IS NULL 的标签，查找其关联的任务及任务所属业务组
    - 如果标签仅被同一个组的任务使用 → 直接更新 group_id
    - 如果标签被多个组的任务使用 → 拆分为独立副本（每个组一份）
    - GLOBAL 任务的标签保持 group_id=NULL
    - 已有 group_id 的标签跳过（幂等）
    """
    from sqlalchemy import text

    # 查找所有 group_id IS NULL 的标签
    rows = db.session.execute(text(
        'SELECT id, name, created_by, create_time, update_time '
        'FROM tags WHERE group_id IS NULL'
    )).fetchall()
    if not rows:
        return

    migrated = 0
    split = 0
    for tag_id, tag_name, created_by, create_time, update_time in rows:
        # 查找该标签关联的任务及其所属业务组
        assocs = db.session.execute(text(
            'SELECT tt.task_id, tg.group_id '
            'FROM task_tags tt '
            'LEFT JOIN task_groups tg ON tt.task_id = tg.task_id '
            'WHERE tt.tag_id = :tid'
        ), {'tid': tag_id}).fetchall()

        if not assocs:
            continue  # 无关联任务，保持 NULL

        # 按 group_id 分组
        groups = {}  # {group_id: [task_id, ...]}
        for task_id, gid in assocs:
            groups.setdefault(gid, []).append(task_id)

        # 去掉 None（GLOBAL 任务），GLOBAL 任务的标签关联保留在原标签上
        group_ids_with_tasks = [g for g in groups if g is not None]

        if not group_ids_with_tasks:
            continue  # 全是 GLOBAL 任务，保持 NULL

        if len(group_ids_with_tasks) == 1:
            # 仅一个组 → 直接更新原标签的 group_id
            target_gid = group_ids_with_tasks[0]
            # GLOBAL 任务的关联也迁移到这个组标签上（合理：标签本身属于该组）
            if None not in groups:
                # 没有 GLOBAL 任务关联，直接更新
                db.session.execute(text(
                    'UPDATE tags SET group_id = :gid WHERE id = :tid'
                ), {'gid': target_gid, 'tid': tag_id})
                migrated += 1
            else:
                # 有 GLOBAL 任务关联：原标签保持 NULL（给 GLOBAL），新建一个组标签
                now = update_time or create_time or ''
                db.session.execute(text(
                    'INSERT INTO tags (name, group_id, created_by, create_time, update_time) '
                    'VALUES (:name, :gid, :cb, :ct, :ut)'
                ), {'name': tag_name, 'gid': target_gid, 'cb': created_by or '',
                    'ct': create_time or '', 'ut': now})
                new_tag_id = db.session.execute(text(
                    'SELECT id FROM tags WHERE name = :name AND group_id = :gid'
                ), {'name': tag_name, 'gid': target_gid}).scalar()
                # 将该组任务的 task_tags 指向新标签
                for task_id in groups[target_gid]:
                    db.session.execute(text(
                        'UPDATE task_tags SET tag_id = :new_tid '
                        'WHERE task_id = :task_id AND tag_id = :old_tid'
                    ), {'new_tid': new_tag_id, 'task_id': task_id, 'old_tid': tag_id})
                split += 1
        else:
            # 多个组 → 为每个组创建独立副本
            for gid in group_ids_with_tasks:
                now = update_time or create_time or ''
                # 检查目标组是否已有同名标签
                existing_id = db.session.execute(text(
                    'SELECT id FROM tags WHERE name = :name AND group_id = :gid'
                ), {'name': tag_name, 'gid': gid}).scalar()
                if not existing_id:
                    db.session.execute(text(
                        'INSERT INTO tags (name, group_id, created_by, create_time, update_time) '
                        'VALUES (:name, :gid, :cb, :ct, :ut)'
                    ), {'name': tag_name, 'gid': gid, 'cb': created_by or '',
                        'ct': create_time or '', 'ut': now})
                    existing_id = db.session.execute(text(
                        'SELECT id FROM tags WHERE name = :name AND group_id = :gid'
                    ), {'name': tag_name, 'gid': gid}).scalar()
                # 将该组任务的 task_tags 指向新/已有标签
                for task_id in groups[gid]:
                    db.session.execute(text(
                        'UPDATE task_tags SET tag_id = :new_tid '
                        'WHERE task_id = :task_id AND tag_id = :old_tid'
                    ), {'new_tid': existing_id, 'task_id': task_id, 'old_tid': tag_id})
                split += 1
            # 如果原标签没有 GLOBAL 任务关联了，清理原标签
            if None not in groups:
                db.session.execute(text(
                    'DELETE FROM task_tags WHERE tag_id = :tid'
                ), {'tid': tag_id})
                db.session.execute(text(
                    'DELETE FROM tags WHERE id = :tid'
                ), {'tid': tag_id})

    db.session.commit()
    if migrated or split:
        print('OK: 标签组隔离迁移 -> 直接归属 %d，拆分 %d' % (migrated, split))


def _ensure_job_log_http_status_column():
    _ensure_job_log_columns()


def _ensure_tags_description_column():
    """tags 表补 description 列（标签说明，OPT-P1-11 增强）。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('tags'):
        return
    cols = {c['name'] for c in insp.get_columns('tags')}
    if 'description' in cols:
        return
    with db.engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE tags ADD COLUMN description VARCHAR(255) NOT NULL DEFAULT ''"
        ))
    print('OK: tags 列已补全 -> description')


def _drop_resource_groups_code_column(backend='sqlite'):
    """移除 resource_groups.code 列（冗余字段）并给 name 加唯一约束。"""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if not insp.has_table('resource_groups'):
        return
    cols = {c['name'] for c in insp.get_columns('resource_groups')}
    if 'code' not in cols:
        return
    if backend == 'mysql':
        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE resource_groups DROP COLUMN code'))
    else:
        with db.engine.begin() as conn:
            conn.execute(text(
                'CREATE TABLE IF NOT EXISTS _rg_tmp AS '
                'SELECT id, name, description, create_time FROM resource_groups'
            ))
            conn.execute(text('DROP TABLE resource_groups'))
            conn.execute(text(
                'CREATE TABLE resource_groups ('
                '  id INTEGER PRIMARY KEY,'
                '  name VARCHAR(64) NOT NULL DEFAULT \'\' UNIQUE,'
                '  description VARCHAR(255) NOT NULL DEFAULT \'\','
                '  create_time BIGINT NOT NULL DEFAULT 0'
                ')'
            ))
            conn.execute(text(
                'INSERT INTO resource_groups (id, name, description, create_time) '
                'SELECT id, name, description, create_time FROM _rg_tmp'
            ))
            conn.execute(text('DROP TABLE _rg_tmp'))
    try:
        with db.engine.begin() as conn:
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_resource_groups_create_time '
                'ON resource_groups (create_time)'
            ))
    except Exception:
        pass
    print('OK: resource_groups 已移除 code 列，name 已加 UNIQUE')


def _migrate_time_columns_to_bigint():
    """将所有时间戳列的 VARCHAR 数据迁移为 BIGINT（百毫秒 UTC）。

    幂等：已经是整数的列跳过。支持 SQLite / MySQL 双后端。
    迁移策略 T-A：将历史本地时间转换为真正的 UTC。
    """
    import time

    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    backend = business_db_backend(str(db.engine.url))

    _TS_COLUMNS = [
        ('job_log', ['create_time', 'started_at', 'finished_at']),
        ('cron_infos', ['created_at', 'updated_at', 'retired_at', 'last_operated_at']),
        ('job_health', ['last_run_at', 'last_success_at', 'last_fail_at', 'updated_at']),
        ('operation_log', ['create_time']),
        ('rbac_audit_logs', ['create_time']),
        ('rbac_users', ['api_token_expires_at', 'create_time', 'last_login_at']),
        ('rbac_registration_requests', ['create_time', 'update_time']),
        ('tags', ['create_time', 'update_time']),
        ('resource_groups', ['create_time']),
    ]

    migrated_total = 0
    for table, columns in _TS_COLUMNS:
        if not insp.has_table(table):
            continue
        existing_cols = {c['name'] for c in insp.get_columns(table)}
        for col in columns:
            if col not in existing_cols:
                continue
            if not _column_needs_migration(table, col, backend):
                continue
            count = _convert_column_data(table, col, backend)
            if count >= 0:
                migrated_total += count
                if backend == 'mysql':
                    _alter_column_to_bigint_mysql(table, col)
    if migrated_total:
        print('OK: 时间戳迁移至 BIGINT 完成 -> %d 行' % migrated_total)
    else:
        print('OK: 时间戳列已是 BIGINT，无需迁移')


def _column_needs_migration(table, col, backend):
    """检测列是否仍包含 VARCHAR 时间数据（需要迁移）。
    注意：纯数字文本（如 '17877473677'）是 VARCHAR 列中存储的有效
    BIGINT 时间戳，不应触发迁移。只有日期格式字符串才需要迁移。
    """
    from sqlalchemy import text

    if backend == 'sqlite':
        row = db.session.execute(text(
            "SELECT %s FROM %s WHERE %s IS NOT NULL "
            "AND %s != '' AND %s != '0' AND typeof(%s) = 'text' "
            "AND %s LIKE '____-__-__%%' LIMIT 1"
            % (col, table, col, col, col, col, col)
        )).fetchone()
        return row is not None
    else:
        row = db.session.execute(text(
            "SELECT %s FROM %s WHERE %s IS NOT NULL "
            "AND %s != '' AND %s != '0' LIMIT 1" % (col, table, col, col, col)
        )).fetchone()
        if row is None:
            return False
        val = row[0]
        return isinstance(val, str) and len(val) >= 10 and val[:4].isdigit()


def _convert_column_data(table, col, backend):
    """将列中的 VARCHAR 时间数据转换为 BIGINT 百毫秒 UTC。返回影响行数。"""
    from sqlalchemy import text

    if backend == 'sqlite':
        sql = (
            "UPDATE %s SET %s = CAST(strftime('%%s', %s, 'utc') AS INTEGER) * 10 "
            "WHERE %s IS NOT NULL AND %s != '' AND typeof(%s) = 'text' "
            "AND %s LIKE '____-__-__%%'"
            % (table, col, col, col, col, col, col)
        )
    else:
        sql = (
            "UPDATE %s SET %s = UNIX_TIMESTAMP(%s) * 10 "
            "WHERE %s IS NOT NULL AND %s != '' AND %s != '0' "
            "AND %s REGEXP '^[0-9]{4}-'"
            % (table, col, col, col, col, col, col)
        )

    with db.engine.begin() as conn:
        result = conn.execute(text(sql))
        count = result.rowcount

    # 空字符串 → 0（默认值）；注意不能清除纯数字文本（如 '17877473677'），
    # 那是 VARCHAR 列中存储的有效 BIGINT 时间戳。
    if backend == 'sqlite':
        cleanup_sql = (
            "UPDATE %s SET %s = 0 WHERE %s = '' "
            "OR (%s IS NOT NULL AND typeof(%s) = 'text' AND CAST(%s AS INTEGER) = 0 AND %s != '0')"
            % (table, col, col, col, col, col, col)
        )
    else:
        cleanup_sql = "UPDATE %s SET %s = 0 WHERE %s = ''" % (table, col, col)
    with db.engine.begin() as conn:
        conn.execute(text(cleanup_sql))

    print('  %s.%s -> %d 行已转换' % (table, col, count))
    return count


def _alter_column_to_bigint_mysql(table, col):
    """MySQL 专用：ALTER COLUMN 类型为 BIGINT。"""
    from sqlalchemy import text

    try:
        with db.engine.begin() as conn:
            conn.execute(text(
                'ALTER TABLE %s MODIFY COLUMN %s BIGINT' % (table, col)
            ))
    except Exception as e:
        print('WARN: ALTER %s.%s 失败: %s' % (table, col, e))


def _rename_log_id_to_trace_id(backend='sqlite'):
    """Rename log_id columns to trace_id across 3 tables (idempotent).

    Tables: job_log.log_id, job_log_items.log_id, job_health.last_run_log_id.
    """
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    insp = sa_inspect(db.engine)
    _RENAMES = [
        ('job_log', 'log_id', 'trace_id'),
        ('job_log_items', 'log_id', 'trace_id'),
        ('job_health', 'last_run_log_id', 'last_run_trace_id'),
    ]
    renamed = []
    for table, old_col, new_col in _RENAMES:
        if not insp.has_table(table):
            continue
        existing = {c['name'] for c in insp.get_columns(table)}
        if new_col in existing:
            continue
        if old_col not in existing:
            continue
        try:
            with db.engine.begin() as conn:
                if backend == 'sqlite':
                    conn.execute(text(
                        'ALTER TABLE %s RENAME COLUMN %s TO %s' % (table, old_col, new_col)
                    ))
                else:
                    col_info = [c for c in insp.get_columns(table) if c['name'] == old_col][0]
                    col_type = str(col_info['type'])
                    nullable = 'NULL' if col_info.get('nullable', True) else 'NOT NULL'
                    default = col_info.get('default', '')
                    default_clause = ("DEFAULT '%s'" % default) if default else ''
                    conn.execute(text(
                        'ALTER TABLE %s CHANGE COLUMN %s %s %s %s %s'
                        % (table, old_col, new_col, col_type, nullable, default_clause)
                    ))
            renamed.append('%s.%s' % (table, new_col))
        except Exception as e:
            print('WARN: rename %s.%s -> %s failed: %s' % (table, old_col, new_col, e))
    if renamed:
        print('OK: log_id -> trace_id 列重命名完成 ->', ', '.join(renamed))
    else:
        print('OK: trace_id 列已存在，无需重命名')


def _cleanup_orphan_health_records():
    """OPT-P0-21: 删除 job_health 中 cron_info_id 在 cron_infos 中不存在的孤儿记录。

    幂等：无孤儿时不做任何操作。
    """
    from sqlalchemy import text

    result = db.session.execute(text(
        'DELETE FROM job_health '
        'WHERE cron_info_id NOT IN (SELECT id FROM cron_infos)'
    ))
    if result.rowcount:
        db.session.commit()
        print('OK: OPT-P0-21 孤儿 job_health 清理 -> %d 行' % result.rowcount)


def _correct_subthreshold_health_ok():
    """方案 A：未满持续异常阈值却标 ok 的历史行改为 unknown。

    条件：health_status='ok' AND consecutive_failures > 0。
    幂等；SQLite / MySQL 同语法。
    """
    from sqlalchemy import text

    result = db.session.execute(text(
        "UPDATE job_health SET health_status = 'unknown' "
        "WHERE health_status = 'ok' AND consecutive_failures > 0"
    ))
    if result.rowcount:
        db.session.commit()
        print('OK: 未满阈值失败 health ok→unknown -> %d 行' % result.rowcount)
    else:
        print('OK: 未满阈值失败 health 无需校正')


def _ensure_id_columns_bigint(backend='sqlite'):
    """OPT-P0-21: MySQL 主键使用 BIGINT AUTO_INCREMENT。

    SQLite 无需操作（INTEGER 底层已支持 8 字节）。
    """
    if backend != 'mysql':
        return
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    targets = [
        ('cron_infos', 'id'),
        ('job_log', 'id'),
        ('job_log_events', 'id'),
    ]
    altered = []
    for table, col in targets:
        if not insp.has_table(table):
            continue
        col_info = [c for c in insp.get_columns(table) if c['name'] == col]
        if not col_info:
            continue
        col_type = str(col_info[0]['type']).upper()
        is_auto = bool(col_info[0].get('autoincrement'))
        if 'BIGINT' in col_type and is_auto:
            continue
        try:
            with db.engine.begin() as conn:
                conn.execute(text(
                    'ALTER TABLE %s MODIFY COLUMN %s BIGINT NOT NULL AUTO_INCREMENT'
                    % (table, col)
                ))
            altered.append('%s.%s' % (table, col))
        except Exception as e:
            print('WARN: ALTER %s.%s -> BIGINT 失败: %s' % (table, col, e))
    if altered:
        print('OK: OPT-P0-21 ID 列升级为 BIGINT ->', ', '.join(altered))


if __name__ == '__main__':
    sys.exit(main())
