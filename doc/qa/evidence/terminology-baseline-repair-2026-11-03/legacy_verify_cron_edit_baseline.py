"""只读生产环境之外的任务编辑缺陷复现；全部数据仅存在于内存 SQLite。

这些断言描述当前缺陷证据，不是未来修复后的验收标准。
运行：.venv-py311/bin/python scripts/verify_cron_edit_baseline.py
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask
from sqlalchemy import event, func, select

from app import db
from app.services.cron_service import update_cron
from datas.model.cron_infos import CronInfos
from datas.model.operation_log import OperationLog
from datas.model.tag import Tag
from datas.model.task_group import TaskGroup
from datas.model.task_tag import TaskTag


def run_case(case):
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                      SQLALCHEMY_TRACK_MODIFICATIONS=False, SECRET_KEY='baseline-only')
    db.init_app(app)
    with app.app_context(), app.test_request_context('/cron_edit', method='POST'):
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.create_all()
        values = dict(task_name='baseline', task_keyword='original', run_date='',
                      day_of_week='', day='', hour='1', minute='0', second='',
                      req_url='https://example.invalid/job', req_method='GET',
                      req_body='', timeout_sec=None, scope_type='GROUP')
        task = CronInfos(**values, status=0, created_at=1, updated_at=1,
                         last_operator_name='original', last_operated_at=1)
        tag = Tag(name='baseline-tag', group_id=7)
        db.session.add_all([task, tag])
        db.session.flush()
        task_id = task.id
        db.session.add_all([TaskGroup(task_id=task_id, group_id=7),
                            TaskTag(task_id=task_id, tag_id=tag.id)])
        db.session.commit()
        requested = dict(values, group_id=7, tag_names=['baseline-tag'])
        if case == 'stale_form':
            # 独立事务先完成提交，再让旧表单调用当前写服务；不是同时写入压测。
            with db.engine.begin() as connection:
                connection.execute(CronInfos.__table__.update().where(
                    CronInfos.id == task_id).values(task_keyword='concurrent-new'))
            db.session.expire_all()
            assert db.session.get(CronInfos, task_id).task_keyword == 'concurrent-new'
        elif case != 'no_change':
            requested['task_keyword'] = 'requested-new'
        statements = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            verb = statement.lstrip().split()[0].upper()
            if verb in ('UPDATE', 'DELETE', 'INSERT'):
                statements.append(statement.splitlines()[0])

        event.listen(db.engine, 'before_cursor_execute', capture)
        real_commit = db.session.commit
        commit_attempts = []

        def commit():
            commit_attempts.append(1)
            if case == 'audit_failure' and len(commit_attempts) == 2:
                raise RuntimeError('baseline: operation log commit failure')
            return real_commit()

        error = None
        returned = False
        with patch('app.services.cron_service.register_cron_job') as register, \
                patch('app.services.cron_service.scheduler') as scheduler, \
                patch.object(db.session, 'commit', side_effect=commit):
            if case == 'scheduler_failure':
                register.side_effect = RuntimeError('baseline: register failure')
            if case == 'pause_failure':
                scheduler.pause_job.side_effect = RuntimeError('baseline: pause failure')
            try:
                update_cron(db.session.get(CronInfos, task_id), requested)
                returned = True
            except RuntimeError as exc:
                error = str(exc)
                db.session.rollback()
            register_calls = register.call_count
            pause_calls = scheduler.pause_job.call_count
        event.remove(db.engine, 'before_cursor_execute', capture)
        db.session.remove()
        stored = db.session.get(CronInfos, task_id)
        log_count = db.session.scalar(select(func.count()).select_from(OperationLog))
        result = dict(case=case, returned=returned, error=error,
                      stored_keyword=stored.task_keyword, updated_at=stored.updated_at,
                      commit_attempts=len(commit_attempts), register_calls=register_calls,
                      pause_calls=pause_calls, operation_logs=log_count, dml=statements)
        if case == 'no_change':
            assert returned and register_calls == 1 and pause_calls == 1
            assert len(commit_attempts) == 2 and log_count == 1 and stored.updated_at != 1
            assert any(s.startswith('DELETE FROM task_groups') for s in statements)
            assert any(s.startswith('DELETE FROM task_tags') for s in statements)
            assert any(s.startswith('INSERT INTO task_groups') for s in statements)
            assert any(s.startswith('INSERT INTO task_tags') for s in statements)
        elif case == 'stale_form':
            assert returned and stored.task_keyword == 'original'
        elif case == 'scheduler_failure':
            assert error and not returned and stored.task_keyword == 'requested-new'
            assert log_count == 0
        elif case == 'audit_failure':
            assert returned and stored.task_keyword == 'requested-new' and log_count == 0
        elif case == 'pause_failure':
            assert returned and stored.status == 0 and log_count == 1
        db.session.remove()
        db.drop_all()
        return result


if __name__ == '__main__':
    for name in ('no_change', 'stale_form', 'scheduler_failure',
                 'audit_failure', 'pause_failure'):
        print(json.dumps(run_case(name), ensure_ascii=False))
    print('BASELINE: 5/5 current defect scenarios reproduced (not fix acceptance)')
