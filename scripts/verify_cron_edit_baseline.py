#!/usr/bin/env python3
"""Verify six current task-edit contracts using owned in-memory fixtures.

The pre-repair experiment is archived under doc/qa/evidence/
terminology-baseline-repair-2026-11-03/legacy_verify_cron_edit_baseline.py.
Its historical defect assertions are not current acceptance criteria.
"""
import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apscheduler.schedulers.background import BackgroundScheduler  # noqa: E402
from flask import Flask, session  # noqa: E402
from flask_apscheduler import APScheduler  # noqa: E402
from sqlalchemy import event, func, select  # noqa: E402

from app import db  # noqa: E402
from app.services.cron_edit_concurrency import build_task_edit_snapshot, save_task_edit  # noqa: E402
from app.services.cron_service import register_cron_job, update_cron  # noqa: E402
from datas.model.cron_infos import CronInfos  # noqa: E402
from datas.model.operation_log import OperationLog  # noqa: E402
from datas.model.rbac_user import RbacUser  # noqa: E402
from datas.model.resource_group import ResourceGroup  # noqa: E402
from datas.model.tag import Tag  # noqa: E402
from datas.model.task_group import TaskGroup  # noqa: E402
from datas.model.task_tag import TaskTag  # noqa: E402
from datas.model.user_group import UserGroup  # noqa: E402

CASES = ('no_change', 'unrelated_merge', 'same_field_conflict',
         'scheduler_failure', 'audit_failure', 'paused_registration')


def require(condition, phase):
    if not condition:
        raise AssertionError(phase)


@contextmanager
def fixture():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='current-baseline-only', SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                      SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    base = BackgroundScheduler(timezone='UTC')
    api = APScheduler(scheduler=base)
    api.app = app
    with app.test_request_context('/cron_edit', method='POST'):
        require(db.engine.url.database == ':memory:', 'business_database_not_memory')
        engine = db.engine
        base.start(paused=True)
        try:
            with patch('app.services.cron_service.scheduler', api), \
                    patch('app.services.cron_edit_apply.scheduler', api), \
                    patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')):
                db.create_all()
                session.update(user_id=1, username='baseline-operator', role='operator')
                values = dict(task_name='baseline', task_keyword='original', run_date='', day_of_week='',
                              day='', hour='1', minute='0', second='', req_url='https://example.invalid/task',
                              req_method='GET', req_body='', timeout_sec=None)
                task = CronInfos(**values, scope_type='GROUP', status=0, created_at=1, updated_at=1,
                                 last_operator_name='original', last_operated_at=1)
                db.session.add_all([task, ResourceGroup(id=7, name='baseline-group'),
                                    Tag(id=1, name='baseline-tag', group_id=7),
                                    RbacUser(id=1, username='baseline-operator', role='operator',
                                             is_active=1, auth_version=0, password_hash='fixture-only')])
                db.session.flush()
                task_id = task.id
                db.session.add_all([UserGroup(user_id=1, group_id=7), TaskGroup(task_id=task_id, group_id=7),
                                    TaskTag(task_id=task_id, tag_id=1)])
                db.session.commit()
                register_cron_job(task_id, values, paused=True)
                token = build_task_edit_snapshot(1, task)
                normalized = dict(values, scope_type='GROUP', group_id=7, tag_names=['baseline-tag'])
                raw = dict(normalized, timeout_sec='', ds_ms='2')
                yield SimpleNamespace(task=task, task_id=task_id, token=token, raw=raw,
                                      normalized=normalized, api=api, base=base)
        finally:
            base.shutdown(wait=True)
            db.session.remove()
            engine.dispose()


def stored(f):
    task = db.session.get(CronInfos, f.task_id)
    return dict(keyword=task.task_keyword, timeout=task.timeout_sec, minute=task.minute,
                status=task.status, revision=task.edit_revision, updated_at=task.updated_at,
                operator=task.last_operator_name, operated_at=task.last_operated_at,
                groups=list(db.session.scalars(select(TaskGroup.group_id).where(TaskGroup.task_id == f.task_id))),
                tags=list(db.session.scalars(select(TaskTag.tag_id).where(TaskTag.task_id == f.task_id))),
                logs=db.session.scalar(select(func.count()).select_from(OperationLog)))


def save(f, **changes):
    return save_task_edit(1, f.task_id, f.token, dict(f.raw, **changes), 0, {})


@contextmanager
def observe(f, audit_failure=False, scheduler_failure=False):
    trace = dict(dml=[], commits=0, committed=0, fault_hits=0)
    concrete = db.session()
    original_commit = concrete.commit

    def capture(_conn, _cursor, sql, _parameters, _context, _many):
        if sql.lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE'):
            trace['dml'].append(sql.splitlines()[0])

    def commit():
        trace['commits'] += 1
        if audit_failure and trace['commits'] == 2:
            trace['fault_hits'] += 1
            raise RuntimeError('verification audit commit failure')
        result = original_commit()
        trace['committed'] += 1
        return result

    def register(*args, **kwargs):
        if scheduler_failure:
            trace['fault_hits'] += 1
            raise RuntimeError('verification scheduler write failure')
        return register_cron_job(*args, **kwargs)

    event.listen(db.engine, 'before_cursor_execute', capture)
    try:
        with patch.object(concrete, 'commit', side_effect=commit), \
                patch('app.services.cron_service.register_cron_job', side_effect=register) as registration, \
                patch.object(f.base, 'pause_job', wraps=f.base.pause_job) as pause, \
                patch.object(f.base, 'resume_job', wraps=f.base.resume_job) as resume:
            yield trace
            trace.update(registrations=registration.call_count, pauses=pause.call_count,
                         resumes=resume.call_count)
    finally:
        event.remove(db.engine, 'before_cursor_execute', capture)


def verify_case(case, before, after, trace, result, job_before, job_after):
    """Fail on observable regressions, including unintended commits and partial saves."""
    relation_dml = [sql for sql in trace['dml'] if 'task_groups' in sql or 'task_tags' in sql]
    require(not relation_dml, 'unexpected_relationship_dml')
    require(after['groups'] == before['groups'] and after['tags'] == before['tags'], 'relationship_changed')
    require(after['status'] == 0, 'paused_status_changed')
    writes = trace['registrations'] + trace['pauses'] + trace['resumes']
    if case in ('no_change', 'same_field_conflict'):
        expected = 'no_change' if case == 'no_change' else 'conflict'
        require(result['outcome'] == expected, 'wrong_read_only_outcome')
        require(after == before, 'read_only_submission_changed_state')
        require(not trace['dml'] and trace['commits'] == writes == 0, 'read_only_submission_has_side_effects')
    else:
        expected = 'saved_scheduler_error' if case == 'scheduler_failure' else 'updated'
        require(result['outcome'] == expected, 'wrong_write_outcome')
        require(after['revision'] == before['revision'] + 1, 'revision_not_incremented_once')
        require(trace['committed'] >= 1, 'business_commit_missing')
        if case == 'unrelated_merge':
            require(after['keyword'] == 'concurrent' and after['timeout'] == 10, 'unrelated_change_lost')
        elif case == 'audit_failure':
            require(after['keyword'] == 'requested', 'business_save_lost_after_audit_failure')
        else:
            require(after['minute'] == '5', 'schedule_target_not_saved')
        audit_delta = 0 if case in ('audit_failure', 'scheduler_failure') else 1
        require(after['logs'] - before['logs'] == audit_delta, 'wrong_audit_effect')
        if case in ('scheduler_failure', 'audit_failure'):
            require(trace['fault_hits'] == 1, 'failure_injection_not_hit_once')
    if case == 'paused_registration':
        require(trace['registrations'] == 1 and trace['pauses'] == trace['resumes'] == 0,
                'paused_registration_uses_follow_up_toggle')
        require(job_after['paused'] and job_after['trigger'] != job_before['trigger'], 'paused_job_target_wrong')
    elif case == 'scheduler_failure':
        require(trace['registrations'] == 1 and trace['pauses'] == trace['resumes'] == 0,
                'scheduler_failure_writes_wrong')
        require(job_after == job_before and '已保存' in result['msg'], 'committed_error_not_reported')
    else:
        require(writes == 0 and job_after == job_before, 'non_schedule_change_touched_job')
    return dict(case=case, outcome=result['outcome'], passed=True, dml_count=len(trace['dml']),
                relationship_dml=len(relation_dml), commit_attempts=trace['commits'],
                committed=trace['committed'], fault_hits=trace['fault_hits'], scheduler_writes=writes,
                revision_delta=after['revision'] - before['revision'],
                audit_delta=after['logs'] - before['logs'], paused=job_after['paused'])


def job_state(f):
    job = f.api.get_job('cron_%s' % f.task_id)
    require(job is not None, 'fixture_job_missing')
    return dict(paused=job.next_run_time is None, trigger=str(job.trigger))


def run_case(case):
    require(case in CASES, 'unknown_case')
    with fixture() as f:
        if case in ('unrelated_merge', 'same_field_conflict'):
            require(save(f, task_keyword='concurrent')['outcome'] == 'updated', 'concurrent_setup_failed')
        before = stored(f)
        job_before = job_state(f)
        with observe(f, audit_failure=case == 'audit_failure', scheduler_failure=case == 'scheduler_failure') as trace:
            if case == 'no_change':
                require(update_cron(f.task, f.normalized) is f.task, 'legacy_model_return_changed')
                result = save(f)
            elif case == 'unrelated_merge':
                result = save(f, timeout_sec='10')
            elif case == 'same_field_conflict':
                result = save(f, task_keyword='mine', timeout_sec='10')
            elif case == 'audit_failure':
                result = save(f, task_keyword='requested')
            else:
                result = save(f, minute='5')
        db.session.expire_all()
        return verify_case(case, before, stored(f), trace, result, job_before, job_state(f))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    completed = []
    for case in CASES:
        try:
            print(json.dumps(run_case(case), ensure_ascii=False), flush=True)
            completed.append(case)
        except Exception as error:
            print('CRON_EDIT_BASELINE: FAIL case=%s type=%s' % (case, type(error).__name__), file=sys.stderr)
            return 1
    if len(completed) != 6 or len(set(completed)) != 6:
        print('CRON_EDIT_BASELINE: FAIL case_matrix_incomplete', file=sys.stderr)
        return 1
    print('CRON_EDIT_BASELINE: OK cases=6 mode=current_contract')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
