#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R2-2E2 注册审批 Scope 查询的隔离双后端验收。

本脚本只接受显式的专用测试数据库 URL。它不读取 conf.ini，不连接开发库，
也不会修改业务代码；MySQL 容器/数据库应由调用方在脚本外创建和销毁。
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import and_, create_engine, func, insert, inspect, or_, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import db
from app.repositories.registration_request_repository import RegistrationRequestRepository
from app.services.pagination import PageQuery
from datas.model.rbac_registration_request import RbacRegistrationRequest
from datas.model.rbac_registration_request_group import RbacRegistrationRequestGroup
from datas.model.resource_group import ResourceGroup

MARKER = 'cronpilot_r2e2_'
DEFAULT_ROWS = 10_000
DEFAULT_PENDING_PERCENT = 10
DEFAULT_ABSOLUTE_P95_MS = 500
DEFAULT_GROUP_IDS = tuple(range(101, 201))


def assert_isolated_database(database_url):
    """拒绝非专用库，避免性能验收误写入开发/生产库。"""
    url = make_url(database_url)
    backend = url.get_backend_name()
    database = str(url.database or '')
    if backend not in ('sqlite', 'mysql'):
        raise ValueError('仅支持 sqlite 或 mysql 专用验收库')
    if MARKER not in database:
        raise ValueError('数据库名/路径必须包含专用标记 %s' % MARKER)
    if backend == 'sqlite':
        path = os.path.realpath(database)
        if not path.startswith('/private/tmp/'):
            raise ValueError('SQLite 验收库必须位于 /private/tmp')
    return backend


def _tables():
    return (
        ResourceGroup.__table__,
        RbacRegistrationRequest.__table__,
        RbacRegistrationRequestGroup.__table__,
    )


def ensure_empty_schema(engine):
    """只在三张验收表均不存在时建表，拒绝复用任何已有数据库。"""
    table_names = [table.name for table in _tables()]
    existing = set(inspect(engine).get_table_names())
    occupied = sorted(existing.intersection(table_names))
    if occupied:
        raise RuntimeError('专用验收库不是空库，拒绝覆盖: %s' % ', '.join(occupied))
    db.metadata.create_all(bind=engine, tables=list(_tables()))


def _request_row(row_id, role, groups, status):
    username = 'r2e2-%06d' % row_id
    return {
        'id': row_id,
        'email': '%s@example.invalid' % username,
        'username': username,
        'password_hash': 'benchmark-not-a-password',
        'role': role,
        'group_ids': ','.join(str(group_id) for group_id in groups),
        'job_title': 'benchmark',
        'nickname': username,
        'reason': 'R2-2E2 isolated benchmark',
        'status': status,
        'reviewer_id': None,
        'review_comment': None,
        'create_time': row_id,
        'update_time': None,
        'pending_username': username if status == 'pending' else None,
        'is_reactivation': 0,
        'target_user_id': None,
    }


def seed_dataset(session, rows, pending_percent=DEFAULT_PENDING_PERCENT):
    """固定构造父行及约 3 倍 concrete 关联行，返回 manifest。"""
    if rows < 1:
        raise ValueError('rows 必须大于 0')
    if pending_percent < 1 or pending_percent > 100:
        raise ValueError('pending_percent 必须位于 1..100')
    group_rows = [
        {'id': group_id, 'name': 'r2e2-group-%s' % group_id,
         'description': 'R2-2E2 benchmark', 'create_time': 0}
        for group_id in DEFAULT_GROUP_IDS
    ]
    # 1/10 冲突样本只用于真值验收，不进入性能 actor 组 (101..110)。
    group_rows.extend([
        {'id': 1, 'name': 'r2e2-group-1', 'description': 'truth-only', 'create_time': 0},
        {'id': 10, 'name': 'r2e2-group-10', 'description': 'truth-only', 'create_time': 0},
    ])
    session.execute(insert(ResourceGroup.__table__), group_rows)

    request_rows = []
    relation_rows = []
    concrete_count = 0
    global_count = 0
    pending_count = 0
    roles = ('viewer', 'operator', 'admin')
    for row_id in range(1, rows + 1):
        role = roles[(row_id - 1) % len(roles)]
        status = (
            'pending'
            if row_id % 100 < pending_percent
            else 'approved'
        )
        if status == 'pending':
            pending_count += 1
        # 仅 admin 的固定小比例为合法 global；其余 concrete 均为三个不同组。
        if role == 'admin' and row_id % 60 == 0:
            request_rows.append(_request_row(row_id, role, ('__ALL__',), status))
            global_count += 1
            continue
        groups = tuple(sorted({
            101 + (row_id * 7) % 100,
            101 + (row_id * 31 + 11) % 100,
            101 + (row_id * 67 + 29) % 100,
        }))
        if len(groups) != 3:
            raise AssertionError('固定种子意外产生重复业务组')
        request_rows.append(_request_row(row_id, role, groups, status))
        relation_rows.extend({
            'registration_request_id': row_id,
            'group_id': group_id,
        } for group_id in groups)
        concrete_count += 1

    truth_start = rows + 1
    truth_rows = [
        _request_row(truth_start, 'viewer', (1,), 'pending'),
        _request_row(truth_start + 1, 'viewer', (10,), 'pending'),
        _request_row(truth_start + 2, 'admin', (1, 10), 'pending'),
        _request_row(truth_start + 3, 'admin', ('__ALL__',), 'pending'),
    ]
    request_rows.extend(truth_rows)
    relation_rows.extend([
        {'registration_request_id': truth_start, 'group_id': 1},
        {'registration_request_id': truth_start + 1, 'group_id': 10},
        {'registration_request_id': truth_start + 2, 'group_id': 1},
        {'registration_request_id': truth_start + 2, 'group_id': 10},
    ])
    pending_count += 4

    # 每批 2,000 行，避免 100k ORM 实体进入 identity map。
    for start in range(0, len(request_rows), 2000):
        session.execute(
            insert(RbacRegistrationRequest.__table__), request_rows[start:start + 2000]
        )
    for start in range(0, len(relation_rows), 5000):
        session.execute(
            insert(RbacRegistrationRequestGroup.__table__),
            relation_rows[start:start + 5000],
        )
    session.commit()
    return {
        'base_requests': rows,
        'total_requests': len(request_rows),
        'concrete_requests': concrete_count,
        'global_requests': global_count + 1,
        'relation_rows': len(relation_rows),
        'pending_requests': pending_count,
        'pending_percent': pending_percent,
        'group_count': len(group_rows),
        'seed': 'deterministic-v2-capacity-calibrated',
    }


def assert_dataset_integrity(session, manifest):
    request_count = session.scalar(select(func.count()).select_from(RbacRegistrationRequest))
    relation_count = session.scalar(select(func.count()).select_from(RbacRegistrationRequestGroup))
    orphan_count = session.scalar(select(func.count()).select_from(RbacRegistrationRequestGroup).where(
        ~RbacRegistrationRequestGroup.registration_request_id.in_(
            select(RbacRegistrationRequest.id)
        )
    ))
    if request_count != manifest['total_requests']:
        raise AssertionError('申请数不守恒: %s != %s' % (request_count, manifest['total_requests']))
    if relation_count != manifest['relation_rows']:
        raise AssertionError('关联数不守恒: %s != %s' % (relation_count, manifest['relation_rows']))
    if orphan_count:
        raise AssertionError('发现孤儿关联: %s' % orphan_count)


def assert_truth_matrix(session, rows):
    repo = RegistrationRequestRepository(session)
    names_for_one = {
        row.username for row in repo.paginate_by_groups(PageQuery(per_page=20), [1]).items
    }
    required = 'r2e2-%06d' % (rows + 1)
    forbidden = {
        'r2e2-%06d' % (rows + 2),
        'r2e2-%06d' % (rows + 3),
    }
    if required not in names_for_one or names_for_one.intersection(forbidden):
        raise AssertionError('组 1/10 与 admin 子集真值矩阵失败')
    names_for_both = {
        row.username for row in repo.paginate_by_groups(PageQuery(per_page=20), [1, 10]).items
    }
    expected = {
        'r2e2-%06d' % (rows + 1),
        'r2e2-%06d' % (rows + 2),
        'r2e2-%06d' % (rows + 3),
    }
    if not expected.issubset(names_for_both):
        raise AssertionError('组 1+10 的精确授权矩阵失败')


def _legacy_viewer_stmt(group_ids):
    request = RbacRegistrationRequest
    predicates = [request.group_ids.like('%%%s%%' % group_id) for group_id in group_ids]
    return select(request).where(
        request.role == 'viewer',
        request.status == 'pending',
        or_(*predicates),
    ).order_by(request.id.desc())


def _new_viewer_stmt(group_ids):
    request = RbacRegistrationRequest
    return select(request).where(
        request.role == 'viewer',
        request.status == 'pending',
        RegistrationRequestRepository._scoped_visibility(group_ids),
    ).order_by(request.id.desc())


def _repository_stmt(group_ids, status=None):
    request = RbacRegistrationRequest
    scoped_ids = RegistrationRequestRepository._scoped_request_ids(
        group_ids,
        status=status,
    ).subquery()
    stmt = select(request).join(scoped_ids, scoped_ids.c.id == request.id)
    if status:
        stmt = stmt.where(request.status == status)
    return stmt.order_by(request.id.desc())


def _count_stmt(stmt):
    return select(func.count()).select_from(stmt.order_by(None).subquery())


def _time_statement(session, statement, mode, warmups, runs):
    def invoke():
        if mode == 'count':
            return int(session.scalar(statement) or 0)
        return tuple(row.id for row in session.scalars(statement).all())

    expected = invoke()
    for _ in range(warmups):
        if invoke() != expected:
            raise AssertionError('预热阶段查询结果不稳定')
    samples = []
    for _ in range(runs):
        started = time.perf_counter()
        actual = invoke()
        elapsed = (time.perf_counter() - started) * 1000
        if actual != expected:
            raise AssertionError('计时阶段查询结果不稳定')
        samples.append(elapsed)
    ordered = sorted(samples)
    p95_index = max(0, int(len(ordered) * 0.95 + 0.999999) - 1)
    return {
        'result_fingerprint': str(expected)[:256],
        'samples_ms': [round(sample, 3) for sample in samples],
        'p50_ms': round(statistics.median(samples), 3),
        'p95_ms': round(ordered[p95_index], 3),
        'max_ms': round(max(samples), 3),
    }


def _explain(session, engine, statement, backend):
    sql = str(statement.compile(engine, compile_kwargs={'literal_binds': True}))
    if backend == 'sqlite':
        rows = session.execute(text('EXPLAIN QUERY PLAN ' + sql)).all()
        rendered = [' | '.join(str(value) for value in row) for row in rows]
        relation_mentions = [line for line in rendered if 'rbac_registration_request_groups' in line]
        index_used = any('USING' in line.upper() and 'INDEX' in line.upper() for line in relation_mentions)
        full_scan = any('SCAN rbac_registration_request_groups' in line and 'USING' not in line.upper() for line in relation_mentions)
        correlated = any('CORRELATED' in line.upper() for line in rendered)
        return {
            'sql': sql,
            'plan': rendered,
            'relation_index_used': index_used,
            'relation_full_scan': full_scan,
            'correlated_subquery': correlated,
        }
    raw = session.execute(text('EXPLAIN FORMAT=JSON ' + sql)).scalar_one()
    plan = json.loads(raw)
    relation_nodes = list(_mysql_relation_table_nodes(plan))
    full_scan = any(
        node.get('access_type', '').lower() == 'all'
        for node in relation_nodes
    )
    allowed_keys = {
        'uq_reg_req_groups_req_group',
        'ix_reg_req_groups_group_req',
    }
    key_allowed = bool(relation_nodes) and any(
        node.get('key') in allowed_keys for node in relation_nodes
    )
    return {
        'sql': sql,
        'plan': plan,
        'relation_index_used': key_allowed,
        'relation_full_scan': full_scan,
        'correlated_subquery': 'EXISTS' in sql.upper(),
    }


def _mysql_relation_table_nodes(value):
    """递归提取 MySQL JSON 计划中的关联表节点，避免父表 ALL 误判为关联表全扫。"""
    if isinstance(value, dict):
        table = value.get('table')
        if isinstance(table, dict) and table.get('table_name') == 'rbac_registration_request_groups':
            yield table
        for child in value.values():
            yield from _mysql_relation_table_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _mysql_relation_table_nodes(child)


def _timed_repository_flow(session, group_ids, status, warmups, runs):
    repo = RegistrationRequestRepository(session)
    page_query = PageQuery(page=1, per_page=20)

    def invoke():
        page = repo.paginate_by_groups(page_query, group_ids, status=status)
        badge = repo.get_pending_count_by_groups(group_ids)
        return page.total, tuple(row.id for row in page.items), badge

    expected = invoke()
    for _ in range(warmups):
        if invoke() != expected:
            raise AssertionError('Repository 预热结果不稳定')
    samples = []
    for _ in range(runs):
        started = time.perf_counter()
        actual = invoke()
        elapsed = (time.perf_counter() - started) * 1000
        if actual != expected:
            raise AssertionError('Repository 计时结果不稳定')
        samples.append(elapsed)
    ordered = sorted(samples)
    p95_index = max(0, int(len(ordered) * 0.95 + 0.999999) - 1)
    return {'p50_ms': round(statistics.median(samples), 3), 'p95_ms': round(ordered[p95_index], 3), 'max_ms': round(max(samples), 3)}


def _concurrent_repository_flow(
    engine, backend, group_ids, status, workers, rounds,
    query_timeout_seconds,
):
    """以独立 Session 模拟短时并发页面读取，返回逐请求延迟。"""
    page_query = PageQuery(page=1, per_page=20)
    samples = []
    expected = None

    def invoke(barrier):
        with Session(engine) as session:
            if backend == 'mysql':
                session.execute(text(
                    'SET SESSION MAX_EXECUTION_TIME = %s'
                    % (int(query_timeout_seconds) * 1000)
                ))
            repo = RegistrationRequestRepository(session)
            barrier.wait()
            started = time.perf_counter()
            page = repo.paginate_by_groups(
                page_query, group_ids, status=status,
            )
            badge = repo.get_pending_count_by_groups(group_ids)
            elapsed = (time.perf_counter() - started) * 1000
            fingerprint = (
                page.total,
                tuple(row.id for row in page.items),
                badge,
            )
            return elapsed, fingerprint

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in range(rounds):
            barrier = threading.Barrier(workers)
            futures = [pool.submit(invoke, barrier) for _ in range(workers)]
            for future in futures:
                elapsed, fingerprint = future.result()
                if expected is None:
                    expected = fingerprint
                elif fingerprint != expected:
                    raise AssertionError('并发阶段查询结果不稳定')
                samples.append(elapsed)
    ordered = sorted(samples)
    p95_index = max(0, int(len(ordered) * 0.95 + 0.999999) - 1)
    return {
        'workers': workers,
        'rounds': rounds,
        'samples_ms': [round(sample, 3) for sample in samples],
        'p50_ms': round(statistics.median(samples), 3),
        'p95_ms': round(ordered[p95_index], 3),
        'max_ms': round(max(samples), 3),
    }


def run_benchmark(
    database_url, rows=DEFAULT_ROWS, warmups=10, runs=50,
    query_timeout_seconds=30, pending_percent=DEFAULT_PENDING_PERCENT,
    absolute_p95_ms=DEFAULT_ABSOLUTE_P95_MS, stress_mode=False,
    include_legacy=True, concurrency=1, concurrent_rounds=10,
    concurrent_p95_ms=1000,
):
    backend = assert_isolated_database(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    try:
        ensure_empty_schema(engine)
        with Session(engine) as session:
            if backend == 'mysql':
                session.execute(text(
                    'SET SESSION MAX_EXECUTION_TIME = %s'
                    % (int(query_timeout_seconds) * 1000)
                ))
            manifest = seed_dataset(session, rows, pending_percent=pending_percent)
            assert_dataset_integrity(session, manifest)
            assert_truth_matrix(session, rows)
            profiles = {
                'group_1': [101],
                'group_3': [101, 102, 103],
                'group_10': list(range(101, 111)),
            }
            profile_results = {}
            for name, group_ids in profiles.items():
                legacy_count = None
                legacy_page = None
                combined_old = None
                modern_count = None
                modern_page = None
                combined_new = None
                ratio = None
                if include_legacy:
                    legacy = _legacy_viewer_stmt(group_ids)
                    modern = _new_viewer_stmt(group_ids)
                    legacy_ids = tuple(row.id for row in session.scalars(legacy).all())
                    modern_ids = tuple(row.id for row in session.scalars(modern).all())
                    if legacy_ids != modern_ids:
                        raise AssertionError('%s 的等价性能样本结果不一致' % name)
                    modern_count = _time_statement(
                        session, _count_stmt(modern), 'count', warmups, runs,
                    )
                    modern_page = _time_statement(
                        session, modern.limit(20), 'page', warmups, runs,
                    )
                    combined_new = modern_count['p95_ms'] + modern_page['p95_ms']
                    legacy_count = _time_statement(
                        session, _count_stmt(legacy), 'count', warmups, runs,
                    )
                    legacy_page = _time_statement(
                        session, legacy.limit(20), 'page', warmups, runs,
                    )
                    combined_old = legacy_count['p95_ms'] + legacy_page['p95_ms']
                    ratio = combined_new / combined_old if combined_old else None
                pending_repo_stmt = _repository_stmt(group_ids, status='pending')
                pending_stmt = _count_stmt(pending_repo_stmt)
                repository_stmt = _repository_stmt(group_ids)
                profile_results[name] = {
                    'group_ids': group_ids,
                    'legacy_count': legacy_count,
                    'modern_count': modern_count,
                    'legacy_page': legacy_page,
                    'modern_page': modern_page,
                    'legacy_page_combined_p95_ms': (
                        round(combined_old, 3) if combined_old is not None else None
                    ),
                    'modern_page_combined_p95_ms': (
                        round(combined_new, 3) if combined_new is not None else None
                    ),
                    'combined_ratio': round(ratio, 3) if ratio is not None else None,
                    'pending_badge': _time_statement(session, pending_stmt, 'count', warmups, runs),
                    'repository_all_page_plus_badge': _timed_repository_flow(
                        session, group_ids, None, warmups, runs,
                    ),
                    'repository_pending_page_plus_badge': _timed_repository_flow(
                        session, group_ids, 'pending', warmups, runs,
                    ),
                    'explain': _explain(
                        session, engine, repository_stmt.limit(20), backend,
                    ),
                }
                if concurrency > 1:
                    profile_results[name]['concurrent_all_page_plus_badge'] = (
                        _concurrent_repository_flow(
                            engine, backend, group_ids, None,
                            concurrency, concurrent_rounds,
                            query_timeout_seconds,
                        )
                    )
                    profile_results[name]['concurrent_pending_page_plus_badge'] = (
                        _concurrent_repository_flow(
                            engine, backend, group_ids, 'pending',
                            concurrency, concurrent_rounds,
                            query_timeout_seconds,
                        )
                    )
            global_stmt = select(RbacRegistrationRequest).where(
                RbacRegistrationRequest.status == 'pending'
            ).order_by(RbacRegistrationRequest.id.desc())
            global_result = {
                'count': _time_statement(session, _count_stmt(global_stmt), 'count', warmups, runs),
                'page': _time_statement(session, global_stmt.limit(20), 'page', warmups, runs),
            }
            failures = []
            for name, result in profile_results.items():
                for flow_name in (
                    'repository_all_page_plus_badge',
                    'repository_pending_page_plus_badge',
                ):
                    p95_ms = result[flow_name]['p95_ms']
                    if not stress_mode and p95_ms > absolute_p95_ms:
                        failures.append(
                            '%s %s p95 %.3fms 超过绝对 SLO %.3fms'
                            % (name, flow_name, p95_ms, absolute_p95_ms)
                        )
                explain = result['explain']
                if not explain['relation_index_used']:
                    failures.append('%s 关联表索引计划不达标' % name)
                if explain['correlated_subquery']:
                    failures.append('%s 仍存在相关子查询' % name)
                if concurrency > 1:
                    for flow_name in (
                        'concurrent_all_page_plus_badge',
                        'concurrent_pending_page_plus_badge',
                    ):
                        p95_ms = result[flow_name]['p95_ms']
                        if not stress_mode and p95_ms > concurrent_p95_ms:
                            failures.append(
                                '%s %s p95 %.3fms 超过并发 SLO %.3fms'
                                % (name, flow_name, p95_ms, concurrent_p95_ms)
                            )
            return {
                'schema_version': 'r2-2e2-benchmark-v2',
                'backend': backend,
                'manifest': manifest,
                'warmups': warmups,
                'runs': runs,
                'absolute_p95_ms': absolute_p95_ms,
                'stress_mode': stress_mode,
                'include_legacy': include_legacy,
                'concurrency': concurrency,
                'concurrent_rounds': concurrent_rounds,
                'concurrent_p95_ms': concurrent_p95_ms,
                'profiles': profile_results,
                'global': global_result,
                'pass': not failures,
                'failures': failures,
            }
    finally:
        engine.dispose()


def _render_markdown(result):
    manifest = result.get('manifest')
    lines = [
        '# R2-2E2 注册审批 Scope 数据库与性能验收',
        '',
        '- 后端：`%s`' % result['backend'],
        '- 结论：`%s`' % ('PASS' if result['pass'] else 'FAIL'),
        '',
    ]
    if manifest:
        lines.extend([
            '- 数据：%s 张申请、%s 条关联、%s 次预热、%s 次计时' % (
                manifest['total_requests'], manifest['relation_rows'],
                result['warmups'], result['runs'],
            ),
            '',
        ])
    lines.extend([
        '| 场景 | 新/旧组合 p95 比（诊断） | 全历史页面+badge p95(ms) | pending 页面+badge p95(ms) | 索引计划 |',
        '| --- | ---: | ---: | ---: | --- |',
    ])
    for name, profile in result.get('profiles', {}).items():
        lines.append('| %s | %s | %s | %s | %s |' % (
            name, profile['combined_ratio'],
            profile['repository_all_page_plus_badge']['p95_ms'],
            profile['repository_pending_page_plus_badge']['p95_ms'],
            'OK' if profile['explain']['relation_index_used'] and not profile['explain']['correlated_subquery'] else 'FAIL',
        ))
    if result['failures']:
        lines.extend(['', '## 失败项', ''])
        lines.extend('- ' + item for item in result['failures'])
    if result.get('concurrency', 1) > 1:
        lines.extend([
            '',
            '## 并发 %s 验收' % result['concurrency'],
            '',
            '| 场景 | 全历史页面+badge p95(ms) | pending 页面+badge p95(ms) |',
            '| --- | ---: | ---: |',
        ])
        for name, profile in result.get('profiles', {}).items():
            lines.append('| %s | %s | %s |' % (
                name,
                profile['concurrent_all_page_plus_badge']['p95_ms'],
                profile['concurrent_pending_page_plus_badge']['p95_ms'],
            ))
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url', required=True)
    parser.add_argument('--json-output', required=True)
    parser.add_argument('--markdown-output', required=True)
    parser.add_argument('--rows', type=int, default=DEFAULT_ROWS)
    parser.add_argument('--warmups', type=int, default=10)
    parser.add_argument('--runs', type=int, default=50)
    parser.add_argument('--query-timeout-seconds', type=int, default=30)
    parser.add_argument('--pending-percent', type=int, default=DEFAULT_PENDING_PERCENT)
    parser.add_argument('--absolute-p95-ms', type=float, default=DEFAULT_ABSOLUTE_P95_MS)
    parser.add_argument(
        '--stress-mode', action='store_true',
        help='100k 压力诊断：报告绝对耗时但不以 SLO 阻断',
    )
    parser.add_argument(
        '--skip-legacy', action='store_true',
        help='容量档跳过不安全 LIKE 基线，仅验收安全查询绝对 SLO',
    )
    parser.add_argument('--concurrency', type=int, default=1)
    parser.add_argument('--concurrent-rounds', type=int, default=10)
    parser.add_argument('--concurrent-p95-ms', type=float, default=1000)
    parser.add_argument('--allow-small', action='store_true', help='仅供自动化小样本自测')
    args = parser.parse_args(argv)
    if args.rows < DEFAULT_ROWS and not args.allow_small:
        parser.error('--rows 不得小于 %s；小样本仅允许 --allow-small 自测' % DEFAULT_ROWS)
    if args.warmups < 1 or args.runs < 1:
        parser.error('--warmups 与 --runs 必须大于 0')
    if args.query_timeout_seconds < 1:
        parser.error('--query-timeout-seconds 必须大于 0')
    if args.pending_percent < 1 or args.pending_percent > 100:
        parser.error('--pending-percent 必须位于 1..100')
    if args.absolute_p95_ms <= 0:
        parser.error('--absolute-p95-ms 必须大于 0')
    if args.concurrency < 1 or args.concurrent_rounds < 1:
        parser.error('--concurrency 与 --concurrent-rounds 必须大于 0')
    if args.concurrent_p95_ms <= 0:
        parser.error('--concurrent-p95-ms 必须大于 0')
    try:
        result = run_benchmark(
            args.database_url, args.rows, args.warmups, args.runs,
            args.query_timeout_seconds, args.pending_percent,
            args.absolute_p95_ms, args.stress_mode,
            not args.skip_legacy,
            args.concurrency, args.concurrent_rounds,
            args.concurrent_p95_ms,
        )
    except Exception as exc:
        result = {
            'schema_version': 'r2-2e2-benchmark-v2',
            'backend': assert_isolated_database(args.database_url),
            'pass': False,
            'failures': ['benchmark_exception:%s' % type(exc).__name__],
            'error_type': type(exc).__name__,
            'profiles': {},
        }
    json_path = Path(args.json_output)
    md_path = Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md_path.write_text(_render_markdown(result), encoding='utf-8')
    print('RESULT:', 'PASS' if result['pass'] else 'FAIL')
    print('JSON:', json_path)
    print('MARKDOWN:', md_path)
    return 0 if result['pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
