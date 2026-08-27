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
from datas.model.task_group import TaskGroup  # noqa: F401,E402
from datas.model.tag import Tag  # noqa: F401,E402
from datas.model.task_tag import TaskTag  # noqa: F401,E402


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
        _ensure_composite_indexes()
        _migrate_group_id_to_task_groups()
        _ensure_tags_group_id_column()
        _migrate_tags_group_isolation()
        _ensure_tags_description_column()
        _drop_resource_groups_code_column(backend=backend)
        _migrate_time_columns_to_bigint()
        from app.rbac.services import ensure_seed_admin, ensure_existing_users_have_token, expire_stale_registrations
        ensure_seed_admin()
        ensure_existing_users_have_token()
        expire_stale_registrations()
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


def _ensure_composite_indexes():
    """补建复合索引（幂等）。

    job_log (cron_info_id, create_time) — 逾期检测和最近执行时间查询
    使用 Loose Index Scan 加速 MAX(create_time) GROUP BY cron_info_id。
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    composite_targets = [
        ('job_log', 'ix_job_log_cron_id_create_time', ['cron_info_id', 'create_time']),
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


if __name__ == '__main__':
    sys.exit(main())
