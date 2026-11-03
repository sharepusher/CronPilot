"""Re-establish the task authorization probe on current APIs; no task fix implied."""
import multiprocessing
from unittest import mock

from sqlalchemy import event, select

from app import db
from app.services.cron_edit_concurrency import build_task_edit_snapshot, save_task_edit
from datas.model.cron_infos import CronInfos
from datas.model.rbac_user import RbacUser
from datas.model.task_group import TaskGroup
from datas.model.user_group import UserGroup
from scripts.user_edit_browser_harness import require
from scripts.user_edit_sqlite_fixture import FileFixture, _mutate_worker, make_app


def _worker(path, run_id, actor_id, task_id, token, raw, ready, release, queue):
    app = make_app(path, run_id)
    try:
        with app.test_request_context('/cron_edit', method='POST'):
            paused = []
            def pause(conn, _cursor, sql, _params, _ctx, _many):
                if sql.lstrip().startswith('SELECT cron_infos.') and not paused:
                    paused.append(True)
                    ready.set()
                    require(release.wait(10), 'task_probe_release_timeout')
            event.listen(db.engine, 'before_cursor_execute', pause)
            try:
                with mock.patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')):
                    result = save_task_edit(actor_id, task_id, token, dict(
                        raw, task_keyword='requested', scope_type='GROUP', group_id=1,
                        tag_names=[]), 0, {})
            finally:
                event.remove(db.engine, 'before_cursor_execute', pause)
            db.session.expire_all()
            task = db.session.get(CronInfos, task_id)
            actor = db.session.get(RbacUser, actor_id)
            queue.put({'outcome': result['outcome'], 'actor_role': actor.role,
                       'stored_value': task.task_keyword})
    except Exception:
        queue.put({'state': 'worker_error'})
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


def probe(directory, mode, run_id, password):
    from scripts.verify_user_edit_sqlite_boundary import _finish_worker, _start_worker
    path = directory / (mode + '_task_probe.sqlite')
    fixture = FileFixture(path, run_id, mode, password)
    users = fixture.fixture('task_probe')
    try:
        with fixture.app.app_context():
            actor = db.session.get(RbacUser, users['actor']['id'])
            actor.role = 'operator'
            raw = dict(task_name='isolated-task', task_keyword='original', run_date='', day_of_week='',
                       day='', hour='1', minute='0', second='', req_url='https://example.invalid/task',
                       req_method='GET', req_body='', timeout_sec='')
            task = CronInfos(**dict(raw, timeout_sec=None), status=0, scope_type='GROUP')
            db.session.add(task)
            db.session.flush()
            task_id = task.id
            gid = db.session.scalar(select(UserGroup.group_id).where(
                UserGroup.user_id == actor.id).order_by(UserGroup.group_id))
            require(gid == 1, 'task_probe_group_fixture_invalid')
            db.session.add(TaskGroup(task_id=task_id, group_id=gid))
            db.session.commit()
            token = build_task_edit_snapshot(actor.id, task)
        context = multiprocessing.get_context('spawn')
        ready, release = context.Event(), context.Event()
        process, queue = _start_worker(_worker, (str(path), run_id, users['actor']['id'],
                                                task_id, token, raw, ready, release))
        try:
            require(ready.wait(10), 'task_probe_read_not_reached')
            mutation = _finish_worker(*_start_worker(_mutate_worker, (
                str(path), run_id, users['actor']['id'], users['target']['id'], 'actor_role')))
            release.set()
            result = _finish_worker(process, queue)
            observed = (mutation['state'] == 'committed' and result['actor_role'] == 'viewer'
                        and result['outcome'] == 'updated' and result['stored_value'] == 'requested')
            return {'mode': mode, 'probe': 'task_authorization', 'mutation': mutation,
                    'result': result, 'remaining_issue_observed': observed,
                    'task_business_modified': False}
        finally:
            release.set()
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
    finally:
        fixture.close()
