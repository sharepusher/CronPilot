"""在每次新建的 MySQL 专用库中观测真实 DML；只删除本次成功创建的库。"""
import argparse
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db
from app.services.cron_edit_concurrency import build_task_edit_snapshot, save_task_edit
from app.services.cron_service import edit_cron_web, update_cron, upsert_cron_by_task_name
from datas.model.cron_infos import CronInfos
from datas.model.operation_log import OperationLog
from datas.model.resource_group import ResourceGroup
from datas.model.tag import Tag
from datas.model.task_group import TaskGroup
from datas.model.task_tag import TaskTag


def verify(port):
    database = 'cronpilot_noop_verify_' + uuid.uuid4().hex
    url = make_url('mysql+pymysql://root@127.0.0.1:%s/?charset=utf8mb4' % port)
    server = create_engine(url, connect_args={'connect_timeout': 5})
    created = False
    results = []
    try:
        with server.begin() as conn:
            conn.execute(text('CREATE DATABASE `%s` CHARACTER SET utf8mb4' % database))
            created = True
        app = Flask(__name__)
        app.config.update(SQLALCHEMY_DATABASE_URI=url.set(database=database),
                          SQLALCHEMY_TRACK_MODIFICATIONS=False, SECRET_KEY='verification')
        db.init_app(app)
        with app.app_context(), app.test_request_context('/cron_edit', method='POST'):
            tables = [m.__table__ for m in (CronInfos, ResourceGroup, TaskGroup, Tag, TaskTag, OperationLog)]
            db.metadata.create_all(db.engine, tables=tables, checkfirst=False)
            values = dict(task_name='mysql-noop', task_keyword='original', run_date='',
                          day_of_week='', day='', hour='1', minute='0', second='',
                          req_url='https://example.invalid/job', req_method='GET',
                          req_body='', timeout_sec=None)
            task = CronInfos(**values, status=0, scope_type='GROUP', created_at=1,
                             updated_at=1, last_operator_name='original', last_operated_at=1)
            group = ResourceGroup(name='verification')
            db.session.add_all([task, group])
            db.session.flush()
            tag = Tag(name='Alpha', group_id=group.id)
            db.session.add(tag)
            db.session.flush()
            db.session.add_all([TaskGroup(task_id=task.id, group_id=group.id),
                                TaskTag(task_id=task.id, tag_id=tag.id)])
            db.session.commit()
            from scripts.ensure_business_tables import _ensure_cron_infos_columns
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE cron_infos DROP COLUMN edit_revision'))
            _ensure_cron_infos_columns(backend='mysql')
            _ensure_cron_infos_columns(backend='mysql')
            db.session.expire_all()
            assert task.edit_revision == 0
            normalized = dict(values, scope_type='GROUP', group_id=group.id, tag_names=['alpha', 'ALPHA'])
            raw = dict(normalized, ds_ms='2', timeout_sec='')
            statements = []

            def capture(conn, cursor, sql, parameters, context, many):
                if sql.lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE'):
                    statements.append(sql)

            event.listen(db.engine, 'before_cursor_execute', capture)
            try:
                for name, action in (
                    ('direct', lambda: update_cron(task, normalized)),
                    ('web', lambda: edit_cron_web(raw, 0, {}, task.id, return_outcome=True)),
                    ('api', lambda: upsert_cron_by_task_name(dict(values, timeout_sec=''), 0, {})),
                ):
                    statements.clear()
                    with patch.object(db.session, 'commit', wraps=db.session.commit) as commit, \
                            patch('app.services.cron_service.register_cron_job') as register, \
                            patch('app.services.cron_service.scheduler') as scheduler:
                        result = action()
                    assert not statements and commit.call_count == 0
                    assert register.call_count == 0 and not scheduler.mock_calls
                    assert (task.updated_at, task.last_operator_name, task.last_operated_at) == (1, 'original', 1)
                    if name == 'web':
                        assert result == (None, None, 'no_change')
                    assert not list(db.session.scalars(select(OperationLog)))
                    results.append({'case': name, 'dml': 0, 'commits': 0, 'scheduler_writes': 0})
                # Real MySQL Web transaction: concurrent description must survive timeout edit.
                from datas.model.rbac_user import RbacUser
                from datas.model.user_group import UserGroup
                db.metadata.create_all(db.engine, tables=[RbacUser.__table__, UserGroup.__table__])
                actor = RbacUser(username='mysql-task-editor', role='operator', password_hash='verification',
                                 is_active=1, auth_version=0)
                db.session.add(actor)
                db.session.flush()
                db.session.add(UserGroup(user_id=actor.id, group_id=group.id))
                db.session.commit()
                actor_id, task_id = actor.id, task.id
                token = build_task_edit_snapshot(actor_id, task)

                def lock_probe(expect_blocked):
                    blocked = False
                    with db.engine.connect() as other:
                        other.execute(text('SET SESSION innodb_lock_wait_timeout=1'))
                        other.commit()
                        try:
                            other.execute(text('SELECT id FROM cron_infos WHERE id=:id FOR UPDATE'),
                                          {'id': task_id}).all()
                        except OperationalError as exc:
                            if getattr(exc.orig, 'args', [None])[0] != 1205:
                                raise
                            blocked = True
                        finally:
                            other.rollback()
                    assert blocked == expect_blocked

                # Negative calibration: same app context still owns a lock.
                db.session.scalar(select(CronInfos).where(CronInfos.id == task_id).with_for_update())
                lock_probe(True)
                db.session.rollback()
                lock_probe(False)
                with db.engine.begin() as connection:
                    connection.execute(text('UPDATE cron_infos SET task_keyword=:name, '
                                            'edit_revision=edit_revision+1 WHERE id=:id'),
                                       {'name': 'other MySQL editor', 'id': task_id})
                with patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')), \
                        patch('app.services.cron_service.register_cron_job',
                              side_effect=RuntimeError('scheduler unavailable')) as register, \
                        patch('app.services.cron_edit_apply.scheduler') as scheduler:
                    result = save_task_edit(actor_id, task_id, token, dict(raw, timeout_sec='10'), 0, {})
                    assert result['outcome'] == 'updated', result
                    db.session.expire_all()
                    task = db.session.get(CronInfos, task_id)
                    assert task.task_keyword == 'other MySQL editor' and task.timeout_sec == 10
                    result = save_task_edit(actor_id, task_id, token, dict(raw, task_keyword='stale MySQL'), 0, {})
                    assert result['outcome'] == 'conflict', result
                    assert register.call_count == 0 and not scheduler.mock_calls
                    lock_probe(False)
                results.append({'case': 'mysql_merge_and_conflict', 'passed': True})
                results.append({'case': 'same_context_lock_release_with_negative_calibration', 'passed': True})
                from app.rbac.services import set_user_groups
                # A live lock on the user row must block the actual group-change service.
                db.session.rollback()
                db.session.execute(text('SET SESSION innodb_lock_wait_timeout=1'))
                db.session.commit()
                with db.engine.connect() as owner:
                    owner.execute(text('SELECT id FROM rbac_users WHERE id=:id FOR UPDATE'), {'id': actor_id})
                    with patch('app.rbac.services.write_audit_log'), \
                            patch('app.rbac.services._invalidate_api_scope_cache'):
                        blocked = set_user_groups(actor_id, [group.id])
                        assert not blocked['ok'], blocked
                    owner.rollback()
                with patch('app.rbac.services.write_audit_log'), \
                        patch('app.rbac.services._invalidate_api_scope_cache'):
                    assert set_user_groups(actor_id, [group.id])['ok']
                results.append({'case': 'actor_group_update_obeys_user_row_lock', 'passed': True})
                from app.services.cron_edit_concurrency import task_edit_values
                from app.services.tag_service import delete_tag

                db.session.rollback()
                task = db.session.scalar(select(CronInfos).where(CronInfos.id == task_id).with_for_update())
                task_edit_values(task, lock=True)
                with db.engine.connect() as other:
                    other.execute(text('SET SESSION innodb_lock_wait_timeout=1'))
                    other.commit()
                    try:
                        other.execute(text("UPDATE tags SET name='Renamed' WHERE id=:id"), {'id': tag.id})
                        raise AssertionError('tag update did not wait for task edit lock')
                    except OperationalError as exc:
                        assert exc.orig.args[0] == 1205
                    finally:
                        other.rollback()
                db.session.rollback()
                old_revision = db.session.get(CronInfos, task_id).edit_revision
                assert delete_tag(tag.id, force=True)[0]
                db.session.expire_all()
                assert db.session.get(CronInfos, task_id).edit_revision == old_revision + 1
                assert not list(db.session.scalars(select(TaskTag).where(TaskTag.task_id == task_id)))
                results.append({'case': 'tag_row_lock_and_forced_delete_revision', 'passed': True})
            finally:
                event.remove(db.engine, 'before_cursor_execute', capture)
                db.session.remove()
                db.engine.dispose()
    finally:
        if created:
            with server.begin() as conn:
                conn.execute(text('DROP DATABASE `%s`' % database))
        server.dispose()
    print(json.dumps({'backend': 'MySQL', 'results': results, 'isolated_database_removed': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=33089)
    verify(parser.parse_args().port)
