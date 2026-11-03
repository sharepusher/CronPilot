#!/usr/bin/env python3
"""U2: 用真实 MySQL 双连接验证用户编辑行锁等待、释放与冲突回滚。"""
import argparse
import json
import os
import re
import sys
import threading
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock

from flask import Flask, has_request_context, request
from sqlalchemy import delete, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import db
from app.rbac.services import (
    build_user_edit_intent,
    build_user_edit_snapshot,
    get_user_group_ids_for_user,
    project_user_edit_values,
    update_user_management,
)
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.user_group import UserGroup
from datas.utils.times import utc_now_hms


class VerificationError(ValueError):
    """Safe diagnostic text only: never include a connection URL or DB error."""


def assert_isolated_database(database_url):
    try:
        url = make_url(database_url)
    except Exception:
        raise VerificationError('数据库 URL 格式无效') from None
    if url.drivername != 'mysql+pymysql':
        raise VerificationError('仅允许 mysql+pymysql 专用验收库')
    if not re.fullmatch(r'cronpilot_user_edit_verify_[0-9a-f]{12}', url.database or ''):
        raise VerificationError('必须使用每次新建的专用验收库')
    return url.database


def _verification_tables():
    # Stable first CREATE is also a collision barrier for concurrent runs.
    return [RbacUser.__table__, ResourceGroup.__table__,
            UserGroup.__table__, RbacAuditLog.__table__]


def prepare_empty_schema(engine, database):
    """Refuse occupied schemas; never delete or silently reuse existing tables."""
    with engine.connect() as connection:
        actual = connection.scalar(text('SELECT DATABASE()'))
        if actual != database:
            raise VerificationError('默认数据库与专用验收库不一致')
        inspector = inspect(connection)
        tables = inspector.get_table_names(schema=database)
        views = inspector.get_view_names(schema=database)
        if tables or views:
            raise VerificationError('专用验收库非空，拒绝覆盖；请使用新库')
        db.metadata.create_all(
            bind=connection, tables=_verification_tables(), checkfirst=False,
        )
        connection.commit()


def _make_app(database_url):
    app = Flask(__name__)
    app.secret_key = 'mysql-user-edit-verification-only'
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if make_url(database_url).drivername == 'mysql+pymysql':
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {'connect_timeout': 5, 'read_timeout': 5, 'write_timeout': 5},
        }
    db.init_app(app)
    return app


def _values(actor_id, target, group_id, nickname):
    original = build_user_edit_snapshot(actor_id, target, [group_id])
    requested = {
        field: original[field]
        for field in ('email', 'nickname', 'job_title', 'role', 'group_ids')
    }
    requested['nickname'] = nickname
    return original, requested


def _run_verification(app, database):
    with app.app_context():
        prepare_empty_schema(db.engine, database)
        group = ResourceGroup(name='U2-MySQL', create_time=utc_now_hms())
        actor = RbacUser(
            username='u2_mysql_admin',
            role='admin',
            is_active=1,
            auth_version=0,
            create_time=utc_now_hms(),
        )
        actor.set_password('verification-only')
        target = RbacUser(
            username='u2_mysql_target',
            role='viewer',
            is_active=1,
            auth_version=0,
            email='u2@example.invalid',
            nickname='original',
            job_title='qa',
            create_time=utc_now_hms(),
        )
        target.set_password('verification-only')
        db.session.add_all([group, actor, target])
        db.session.flush()
        db.session.add(UserGroup(user_id=target.id, group_id=group.id))
        db.session.commit()
        actor_id, target_id, group_id = actor.id, target.id, group.id
        original, requested = _values(actor_id, target, group_id, 'after-lock')
        engine = db.engine

    result_box = {}

    def run_update():
        try:
            with app.test_request_context('/rbac/users/edit', method='POST'):
                result_box['result'] = update_user_management(
                    actor_id,
                    target_id,
                    original,
                    requested,
                    build_user_edit_intent(original, requested),
                )
        except Exception:  # pragma: no cover - diagnostic boundary
            result_box['error'] = '写线程执行失败'

    with engine.connect() as blocker:
        blocker_tx = blocker.begin()
        blocker.execute(
            text('SELECT id FROM rbac_users WHERE id = :id FOR UPDATE'),
            {'id': target_id},
        ).all()
        worker = threading.Thread(target=run_update, daemon=True)
        worker.start()
        time.sleep(0.5)
        if not worker.is_alive():
            raise AssertionError('写线程未等待目标用户行锁')
        blocker_tx.commit()
        worker.join(timeout=10)
        if worker.is_alive():
            raise AssertionError('释放行锁后写线程仍未结束')
    if result_box.get('error'):
        raise AssertionError(result_box['error'])
    result = result_box.get('result') or {}
    if not result.get('ok') or result.get('outcome') != 'updated':
        raise AssertionError('锁释放后的更新结果异常: %r' % result)

    with reserved_probe(engine) as probe, app.test_request_context('/rbac/users/edit', method='POST'):
        target = db.session.get(RbacUser, target_id)
        if target.nickname != 'after-lock':
            raise AssertionError('锁释放后的资料未写入')
        audit_count = db.session.scalar(
            select(db.func.count()).select_from(RbacAuditLog)
        )
        if audit_count != 1:
            raise AssertionError('业务与审计未形成单次原子结果')
        conflict_original, conflict_requested = _values(
            actor_id, target, group_id, 'requested-after-conflict'
        )
        target.nickname = 'concurrent-value'
        db.session.commit()
        observation = measure_service_exit(
            db.session(), probe,
            lambda: update_user_management(
                actor_id, target_id, conflict_original, conflict_requested,
                build_user_edit_intent(conflict_original, conflict_requested),
            ), [('rbac_users', target_id)], 'conflict',
        )
        lock_elapsed = observation['resources'][0]['elapsed_ms'] / 1000

    with app.app_context():
        target = db.session.get(RbacUser, target_id)
        if target.nickname != 'concurrent-value':
            raise AssertionError('冲突路径覆盖了数据库当前值')
        audit_count = db.session.scalar(
            select(db.func.count()).select_from(RbacAuditLog)
        )
        if audit_count != 1:
            raise AssertionError('冲突路径产生了成功审计')

    print(
        'MYSQL_USER_EDIT_U2: OK '
        'isolated_schema=1 lock_wait_observed=1 conflict=1 lock_release_ms=%.1f audit_rows=1'
        % (lock_elapsed * 1000)
    )
    _verify_partial_scope(app, actor_id, target_id, group_id)
    return _verify_lock_release_matrix(app)


def _verify_partial_scope(app, actor_id, target_id, group_id):
    """R5: exercise projected intent and full authorization conflicts on MySQL."""
    with app.test_request_context('/rbac/users/edit', method='POST'):
        extra = [ResourceGroup(name=name, create_time=utc_now_hms())
                 for name in ('R5-outside', 'R5-editable', 'R5-concurrent')]
        db.session.add_all(extra)
        db.session.flush()
        outside, editable, concurrent = [group.id for group in extra]
        db.session.add_all([
            UserGroup(user_id=actor_id, group_id=group_id),
            UserGroup(user_id=actor_id, group_id=editable),
            UserGroup(user_id=target_id, group_id=outside),
        ])
        db.session.commit()
        target = db.session.get(RbacUser, target_id)
        version, token = target.auth_version, target.api_token

        def values():
            original = build_user_edit_snapshot(
                actor_id, target, get_user_group_ids_for_user(target_id),
            )
            return original, project_user_edit_values(original)

        def save(original, requested):
            return update_user_management(actor_id, target_id, original, requested,
                                          build_user_edit_intent(original, requested))

        original, requested = values()
        assert not build_user_edit_intent(original, requested)
        requested['nickname'] = 'R5-profile-only'
        assert save(original, requested)['ok']
        target = db.session.get(RbacUser, target_id)
        assert (target.auth_version, target.api_token) == (version, token)
        assert get_user_group_ids_for_user(target_id) == sorted([group_id, outside])
        audit = db.session.scalar(select(RbacAuditLog).order_by(RbacAuditLog.id.desc()))
        import json

        assert set(json.loads(audit.detail)['changes']) == {'nickname'}
        original, requested = values()
        requested['group_ids'] = [editable]
        assert save(original, requested)['ok']
        assert get_user_group_ids_for_user(target_id) == sorted([editable, outside])
        assert db.session.get(RbacUser, target_id).auth_version == version + 1
        assert save(original, requested)['outcome'] == 'already_applied'
        original, requested = values()
        requested['group_ids'] = [group_id]
        db.session.execute(delete(UserGroup).where(
            UserGroup.user_id == target_id, UserGroup.group_id == outside,
        ))
        db.session.add(UserGroup(user_id=target_id, group_id=concurrent))
        db.session.commit()
        assert save(original, requested)['outcome'] == 'conflict'
        assert get_user_group_ids_for_user(target_id) == sorted([editable, concurrent])
        original, requested = values()
        requested['nickname'] = 'R5-concurrent-profile'
        db.session.execute(delete(UserGroup).where(
            UserGroup.user_id == target_id, UserGroup.group_id == concurrent,
        ))
        db.session.add(UserGroup(user_id=target_id, group_id=outside))
        db.session.commit()
        assert save(original, requested)['ok']
        assert get_user_group_ids_for_user(target_id) == sorted([editable, outside])
    print('MYSQL_USER_EDIT_R5: OK profile_only=1 outside_preserved=1 replay=1 '
          'auth_conflict=1 concurrent_profile=1')


def require(condition, phase):
    """Only fixed diagnostic phase identifiers reach CLI errors."""
    if not condition:
        raise VerificationError(phase)


class LockProbe:
    """An independently reserved physical connection, never an ORM Session."""

    TABLES = frozenset({'rbac_users', 'user_groups', 'resource_groups'})

    def __init__(self, connection):
        self.connection = connection
        self.connection_id = connection.scalar(text('SELECT CONNECTION_ID()'))
        self.original_timeout = int(connection.scalar(text('SELECT @@session.innodb_lock_wait_timeout')))
        connection.execute(text('SET SESSION innodb_lock_wait_timeout = 1'))
        connection.commit()

    def lock(self, table, key):
        require(table in self.TABLES and type(key) is int, 'probe_resource_invalid')
        started = time.monotonic()
        transaction = self.connection.begin()
        try:
            rows = self.connection.execute(
                text('SELECT id FROM ' + table + ' WHERE id = :id FOR UPDATE'), {'id': key},
            ).all()
            require([row[0] for row in rows] == [key], 'probe_row_missing')
            return {'table': table, 'id': key, 'state': 'acquired', 'row_count': 1,
                    'elapsed_ms': round((time.monotonic() - started) * 1000, 3)}
        except OperationalError as exc:
            code = exc.orig.args[0] if getattr(exc.orig, 'args', ()) else None
            if code != 1205:
                raise VerificationError('probe_query_failed') from None
            return {'table': table, 'id': key, 'state': 'blocked', 'error_code': 1205,
                    'elapsed_ms': round((time.monotonic() - started) * 1000, 3)}
        finally:
            transaction.rollback()

    def restore(self):
        try:
            self.connection.rollback()
            self.connection.execute(
                text('SET SESSION innodb_lock_wait_timeout = :value'),
                {'value': self.original_timeout},
            )
            self.connection.commit()
        except Exception:
            self.connection.invalidate()
            raise VerificationError('probe_cleanup_failed') from None


@contextmanager
def reserved_probe(engine):
    with engine.connect() as connection:
        probe = None
        try:
            probe = LockProbe(connection)
            yield probe
        finally:
            if probe is not None:
                probe.restore()
            else:
                connection.invalidate()


def capture_exit(session, request_identity):
    """No SQL here: querying an expired ORM object would change the observation."""
    require(has_request_context(), 'request_ended_before_probe')
    require(request._get_current_object() is request_identity, 'request_changed_before_probe')
    require(db.session() is session, 'session_replaced_before_probe')
    return session.in_transaction(), session.get_transaction()


def measure_service_exit(session, probe, call, resources, expected, *,
                         omit_rollback=False, fail_after_flush=False, teardown_control=False):
    """Observe before any harness cleanup; mutations affect this Session only."""
    identity = request._get_current_object()
    engine = db.engine
    timeline = ['service_enter']
    state = {'writer_id': None, 'connection': None, 'locked': False,
             'suppressed': 0, 'dml': 0, 'commits': 0, 'flushed': False}
    real_rollback, real_flush = session.rollback, session.flush

    def after_begin(_session, _transaction, connection):
        state['connection'] = connection
        state['writer_id'] = connection.scalar(text('SELECT CONNECTION_ID()'))

    def after_sql(connection, cursor, statement, parameters, context, many):
        if connection is not state['connection']:
            return
        sql = statement.strip().upper()
        if 'FOR UPDATE' in sql:
            state['locked'] = True
        if sql.startswith(('INSERT ', 'UPDATE ', 'DELETE ')):
            state['dml'] += 1

    def after_commit(_session):
        state['commits'] += 1

    def rollback():
        if state['locked']:
            state['suppressed'] += 1
            require(state['suppressed'] == 1, 'mutation_multiple_terminal_rollbacks')
            return
        return real_rollback()

    def flush(*args, **kwargs):
        previous_dml = state['dml']
        result = real_flush(*args, **kwargs)
        if state['dml'] == previous_dml:
            return result
        if session.new or session.dirty or session.deleted:
            raise VerificationError('flush_injection_not_after_dml')
        state['flushed'] = True
        raise RuntimeError('verification: failure after real flush')

    event.listen(session, 'after_begin', after_begin)
    event.listen(session, 'after_commit', after_commit)
    event.listen(engine, 'after_cursor_execute', after_sql)
    try:
        with ExitStack() as patches:
            if omit_rollback:
                patches.enter_context(mock.patch.object(session, 'rollback', side_effect=rollback))
            if fail_after_flush:
                patches.enter_context(mock.patch.object(session, 'flush', side_effect=flush))
            result = call()
            timeline.append('service_return')
            active, transaction = capture_exit(session, identity)
            require(result.get('outcome') == expected, 'unexpected_service_outcome')
            require(state['locked'], 'service_lock_sql_missing')
            require(state['writer_id'] is not None
                    and state['writer_id'] != probe.connection_id, 'probe_not_independent')
            observations = [probe.lock(table, key) for table, key in resources]
            require(bool(observations), 'probe_resources_empty')
            now_active, now_transaction = capture_exit(session, identity)
            require((active, transaction) == (now_active, now_transaction), 'writer_changed_during_probe')
            expected_state = 'blocked' if omit_rollback else 'acquired'
            require(all(item['state'] == expected_state for item in observations), 'lock_release_mismatch')
            if expected != 'updated':
                require(active is omit_rollback, 'terminal_transaction_state_mismatch')
                require(state['commits'] == 0, 'noncommit_terminal_committed')
            if omit_rollback:
                require(state['suppressed'] == 1, 'mutation_not_activated')
            if fail_after_flush:
                require(state['flushed'] and state['dml'] > 0, 'real_flush_not_observed')
            elif expected != 'updated':
                require(state['dml'] == 0, 'readonly_terminal_wrote_dml')
            timeline.append('probe_complete')
            return {'outcome': expected, 'writer_connection_id': state['writer_id'],
                    'probe_connection_id': probe.connection_id, 'context_alive': True,
                    'transaction_active_at_return': active, 'resources': observations,
                    'mutation_detected': omit_rollback, 'suppressed_rollbacks': state['suppressed'],
                    'dml_count': state['dml'], 'commit_count': state['commits'], 'timeline': timeline}
    finally:
        event.remove(session, 'after_begin', after_begin)
        event.remove(session, 'after_commit', after_commit)
        event.remove(engine, 'after_cursor_execute', after_sql)
        if not teardown_control:
            real_rollback()
            timeline.append('cleanup')


def _business_state(engine, target_id):
    """Sensitive values are compared in memory and never included in reports."""
    with engine.connect() as connection:
        user = dict(connection.execute(select(RbacUser.__table__).where(
            RbacUser.id == target_id,
        )).mappings().one())
        groups = sorted(connection.scalars(select(UserGroup.group_id).where(
            UserGroup.user_id == target_id,
        )).all())
        audits = connection.scalar(select(db.func.count()).select_from(RbacAuditLog))
        return {'user': user, 'groups': groups, 'audits': audits}


def _release_fixture(case):
    """New users per case; never clear another run's data."""
    groups = [ResourceGroup(name=case + name, create_time=utc_now_hms()) for name in ('-A', '-B', '-C')]
    actor = RbacUser(username=case + '-actor', password_hash='verification-only', role='admin',
                     is_active=1, auth_version=0, create_time=utc_now_hms())
    target = RbacUser(username=case + '-target', password_hash='verification-only', role='viewer',
                      is_active=1, auth_version=0, email='fixture@example.invalid', nickname='original',
                      job_title='qa', api_token='fixture-' + case, create_time=utc_now_hms())
    db.session.add_all(groups + [actor, target])
    db.session.flush()
    a, b, c = [group.id for group in groups]
    db.session.add_all([UserGroup(user_id=actor.id, group_id=a),
                        UserGroup(user_id=actor.id, group_id=c),
                        UserGroup(user_id=target.id, group_id=a),
                        UserGroup(user_id=target.id, group_id=b)])
    db.session.commit()
    original = build_user_edit_snapshot(actor.id, target, [a, b])
    requested = project_user_edit_values(original)
    requested['nickname'] = 'requested'
    return actor, target, (a, b, c), original, requested


def _calibrate_probe(app, engine):
    with reserved_probe(engine) as probe, app.test_request_context('/'):
        actor, target, groups, original, requested = _release_fixture('lock-calibration')
        target_id = target.id
        db.session.rollback()
        writer_id = db.session.scalar(text('SELECT CONNECTION_ID()'))
        db.session.execute(select(RbacUser.id).where(RbacUser.id == target_id).with_for_update()).all()
        require(writer_id != probe.connection_id, 'calibration_same_connection')
        held = probe.lock('rbac_users', target_id)
        require(held['state'] == 'blocked', 'calibration_did_not_block')
        db.session.rollback()
        released = probe.lock('rbac_users', target_id)
        require(released['state'] == 'acquired', 'calibration_did_not_release')
        return {'case_id': 'calibration', 'held': held, 'released': released,
                'writer_connection_id': writer_id, 'probe_connection_id': probe.connection_id}


def _verify_release_case(app, engine, case, *, mutation=False):
    case_id = case + ('-mutation' if mutation else '')
    with reserved_probe(engine) as probe:
        with app.test_request_context('/rbac/users/edit', method='POST'):
            actor, target, groups, original, requested = _release_fixture(case_id)
            actor_id, target_id = actor.id, target.id
            expected = 'failed'
            if case == 'profile-conflict':
                target.nickname = 'concurrent'
                expected = 'conflict'
            elif case == 'auth-conflict':
                target.role = 'operator'
                requested['group_ids'] = [groups[2]]
                expected = 'conflict'
            elif case == 'already-applied':
                target.nickname = 'requested'
                expected = 'already_applied'
            elif case == 'actor-denied':
                actor.role = 'viewer'
            elif case == 'target-disabled':
                target.is_active = 0
            elif case == 'scope-drift':
                db.session.execute(delete(UserGroup).where(
                    UserGroup.user_id == actor_id, UserGroup.group_id == groups[2],
                ))
            elif case == 'missing-reason':
                requested['email'] = None
            elif case == 'flush-failed':
                requested['role'] = 'operator'
            elif case == 'updated':
                expected = 'updated'
            else:
                raise VerificationError('unknown_release_case')
            db.session.commit()
            resources = [('rbac_users', actor_id), ('rbac_users', target_id)]
            if case not in ('actor-denied', 'target-disabled'):
                resources += [('user_groups', key) for key in db.session.scalars(
                    select(UserGroup.id).where(UserGroup.user_id.in_([actor_id, target_id])),
                ).all()]
                if case != 'scope-drift':
                    resources += [('resource_groups', key) for key in requested['group_ids']]
            db.session.rollback()
            before = _business_state(engine, target_id)
            concrete = db.session()
            teardown_control = mutation and case == 'profile-conflict'
            with mock.patch('app.rbac.services._invalidate_api_scope_cache') as cache:
                observation = measure_service_exit(
                    concrete, probe,
                    lambda: update_user_management(actor_id, target_id, original, requested,
                                                    build_user_edit_intent(original, requested)),
                    resources, expected, omit_rollback=mutation,
                    fail_after_flush=case == 'flush-failed', teardown_control=teardown_control,
                )
                require(cache.call_count == 0, 'unexpected_cache_side_effect')
        observation['timeline'].append('context_exit')
        if teardown_control:
            require(not concrete.in_transaction(), 'teardown_did_not_end_transaction')
            after_teardown = probe.lock('rbac_users', target_id)
            require(after_teardown['state'] == 'acquired', 'teardown_did_not_release')
            observation['after_teardown'] = after_teardown
        after = _business_state(engine, target_id)
        if expected == 'updated':
            expected_after = dict(before['user'], nickname='requested')
            require(after == dict(before, user=expected_after, audits=before['audits'] + 1),
                    'updated_business_or_audit_mismatch')
        else:
            require(after == before, 'terminal_business_or_audit_changed')
        observation.update(case_id=case_id, business_verified=True, cleanup_verified=True)
        return observation


def _verify_lock_release_matrix(app):
    with app.app_context():
        engine = db.engine
        engines = db.session.execute(text(
            'SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()'
        )).scalars().all()
        require(len(engines) == 4 and all(value == 'InnoDB' for value in engines), 'innodb_required')
    results = [_calibrate_probe(app, engine)]
    for case in ('profile-conflict', 'auth-conflict', 'already-applied', 'actor-denied',
                 'target-disabled', 'scope-drift', 'missing-reason', 'flush-failed', 'updated'):
        results.append(_verify_release_case(app, engine, case))
    for case in ('profile-conflict', 'already-applied', 'missing-reason'):
        results.append(_verify_release_case(app, engine, case, mutation=True))
    print('MYSQL_USER_EDIT_LOCK_RELEASE: OK normal_cases=9 mutations_detected=3 '
          'calibration=1 teardown_contrast=1')
    return {'status': 'passed', 'cases': results}


def verify(database_url):
    database = assert_isolated_database(database_url)
    engine = None
    try:
        app = _make_app(database_url)
        with app.app_context():
            engine = db.engine
        return _run_verification(app, database)
    except VerificationError:
        raise
    except Exception:
        # MySQL DDL may already have committed. Preserve the schema for
        # inspection; an outer disposable-instance owner handles cleanup.
        raise VerificationError('验收未完成；已保留专用库，请检查连接权限或验收阶段') from None
    finally:
        if engine is not None:
            engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-url', required=True)
    parser.add_argument('--json-output', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.database_url)
        if args.json_output:
            output = args.json_output.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    except VerificationError as exc:
        print('MYSQL_USER_EDIT_U2: FAILED %s' % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
