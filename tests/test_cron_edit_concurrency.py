"""并发编辑契约：有效差异、原始基线与数据库版本条件。"""
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import event, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app import db
from app.services.cron_edit_concurrency import (
    _serializer,
    build_task_edit_snapshot,
    save_task_edit,
)
from app.services.cron_service import toggle_status
from app.services.tag_service import delete_tag, update_tag
from datas.model.cron_infos import CronInfos
from datas.model.operation_log import OperationLog
from datas.model.rbac_user import RbacUser
from datas.model.task_group import TaskGroup
from datas.model.task_tag import TaskTag
from tests import test_cron_edit_noop as noop_tests


class TestTaskEditConcurrency(unittest.TestCase):
    setUp = noop_tests.TestCronEditNoop.setUp
    tearDown = noop_tests.TestCronEditNoop.tearDown

    def token(self):
        return build_task_edit_snapshot(1, self.task)

    def save(self, token, **changes):
        with patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')), \
                patch('app.services.cron_service.register_cron_job'), \
                patch('app.services.cron_edit_apply.scheduler'):
            return save_task_edit(1, self.task_id, token, dict(self.raw, **changes), 0, {})

    def test_unrelated_update_is_preserved_and_no_relation_dml(self):
        token = self.token()
        self.task.task_keyword = 'other editor'
        db.session.commit()
        self.sql.clear()
        result = self.save(token, timeout_sec='10')
        self.assertEqual(result['outcome'], 'updated', result)
        current = db.session.get(CronInfos, self.task_id)
        self.assertEqual((current.task_keyword, current.timeout_sec), ('other editor', 10))
        self.assertEqual(current.edit_revision, 2)
        self.assertFalse(any(('task_groups' in sql or 'task_tags' in sql) for sql in self.sql))

    def test_non_schedule_edits_succeed_when_scheduler_unavailable(self):
        changes = [
            {'task_keyword': 'new description'},
            {'req_url': 'https://example.invalid/other'},
            {'req_method': 'POST'},
            {'req_body': '{"value": 1}'},
            {'timeout_sec': '12'},
            {'tag_names': ['newtag']},
        ]
        raw = dict(self.raw)
        with patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')), \
                patch('app.services.cron_service.register_cron_job', side_effect=RuntimeError('unavailable')) as reg, \
                patch('app.services.cron_edit_apply.scheduler') as sched:
            for change in changes:
                with self.subTest(change=change):
                    token = self.token()
                    raw.update(change)
                    result = save_task_edit(1, self.task_id, token, dict(raw), 0, {})
                    self.assertEqual(result['outcome'], 'updated', result)
            reg.assert_not_called()
            self.assertEqual(sched.mock_calls, [])

    def test_schedule_or_resume_change_still_applies_scheduler_once(self):
        token = self.token()
        with patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')), \
                patch('app.services.cron_service.register_cron_job') as reg, \
                patch('app.services.cron_edit_apply.scheduler') as sched:
            result = save_task_edit(1, self.task_id, token,
                                    dict(self.raw, minute='5', task_keyword='mixed'), 0, {})
            self.assertEqual(result['outcome'], 'updated', result)
            reg.assert_called_once()
            sched.pause_job.assert_not_called()
        db.session.expire_all()
        token = self.token()
        raw = dict(self.raw, minute='5', task_keyword='mixed', resume_after_save='1')
        with patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')), \
                patch('app.services.cron_service.register_cron_job') as reg, \
                patch('app.services.cron_edit_apply.scheduler') as sched:
            result = save_task_edit(1, self.task_id, token, raw, 0, {})
            self.assertEqual(result['outcome'], 'updated', result)
            reg.assert_called_once()
            sched.pause_job.assert_not_called()

    def test_group_change_does_not_touch_scheduler(self):
        from datas.model.resource_group import ResourceGroup
        from datas.model.user_group import UserGroup

        db.session.add_all([ResourceGroup(id=8, name='other group'), UserGroup(user_id=1, group_id=8)])
        db.session.commit()
        token = self.token()
        with patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')), \
                patch('app.services.cron_service.register_cron_job', side_effect=RuntimeError('unavailable')) as reg, \
                patch('app.services.cron_edit_apply.scheduler') as sched:
            result = save_task_edit(1, self.task_id, token,
                                    dict(self.raw, group_id='8', tag_names=[]), 0, {})
        self.assertEqual(result['outcome'], 'updated', result)
        self.assertEqual(list(db.session.scalars(select(TaskGroup.group_id))), [8])
        reg.assert_not_called()
        self.assertEqual(sched.mock_calls, [])

    def test_same_field_conflict_rejects_entire_submission(self):
        token = self.token()
        self.task.task_keyword = 'other editor'
        db.session.commit()
        self.sql.clear()
        result = self.save(token, task_keyword='my change', timeout_sec='10')
        self.assertEqual(result['outcome'], 'conflict')
        self.assertEqual(self.sql, [])
        current = db.session.get(CronInfos, self.task_id)
        self.assertEqual(current.task_keyword, 'other editor')
        self.assertIsNone(current.timeout_sec)

    def test_equivalent_update_has_no_writes_or_success_audit(self):
        token = self.token()
        self.task.task_keyword = 'same target'
        db.session.commit()
        self.sql.clear()
        result = self.save(token, task_keyword='same target')
        self.assertEqual(result['outcome'], 'already_applied')
        self.assertEqual(self.sql, [])
        self.assertEqual(list(db.session.scalars(select(OperationLog))), [])

    def test_untouched_fields_preserve_concurrent_tag_removal(self):
        token = self.token()
        delete_tag(1, force=True)
        self.sql.clear()
        result = self.save(token, task_keyword='new description')
        self.assertEqual(result['outcome'], 'updated', result)
        self.assertEqual(list(db.session.scalars(select(TaskTag))), [])
        self.assertFalse(any('task_tags' in sql for sql in self.sql))

    def test_relation_intent_conflicts_with_concurrent_relation_change(self):
        token = self.token()
        delete_tag(1, force=True)
        result = self.save(token, tag_names=['Different'])
        self.assertEqual(result['outcome'], 'conflict')

    def test_tag_rename_preserves_unedited_relation_and_conflicts_on_tag_edit(self):
        token = self.token()
        self.assertTrue(update_tag(1, new_name='Renamed')[0])
        result = self.save(token, task_keyword='description after rename')
        self.assertEqual(result['outcome'], 'updated', result)
        self.assertEqual(db.session.get(noop_tests.Tag, 1).name, 'Renamed')
        self.assertEqual(self.save(token, tag_names=['Different'])['outcome'], 'conflict')
        self.assertEqual(list(db.session.scalars(select(TaskTag.tag_id))), [1])

    def test_tag_delete_without_force_rechecks_new_association(self):
        db.session.execute(TaskTag.__table__.delete())
        db.session.commit()
        injected = []

        def add_after_count(conn, _cursor, statement, _parameters, _context, _executemany):
            if not injected and 'SELECT task_tags.task_id' in statement:
                injected.append(True)
                conn.execute(TaskTag.__table__.insert().values(task_id=self.task_id, tag_id=1))

        event.listen(db.engine, 'before_cursor_execute', add_after_count)
        try:
            ok, message, _ = delete_tag(1, force=False)
        finally:
            event.remove(db.engine, 'before_cursor_execute', add_after_count)
        self.assertTrue(injected)
        self.assertFalse(ok)
        self.assertIn('重新确认', message)
        self.assertIsNotNone(db.session.get(noop_tests.Tag, 1))

    def test_current_actor_downgrade_rejects_stale_form(self):
        token = self.token()
        db.session.get(RbacUser, 1).role = 'viewer'
        db.session.commit()
        self.sql.clear()
        result = self.save(token, task_keyword='must not write')
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(self.sql, [])

    def test_group_change_locks_user_before_group_writes(self):
        from app.rbac.services import set_user_groups
        from datas.model.resource_group import ResourceGroup

        db.session.add(ResourceGroup(id=8, name='other group'))
        db.session.commit()
        events = []

        def watch_orm(execute_state):
            statement = execute_state.statement
            if getattr(statement, '_for_update_arg', None) is not None:
                events.append('lock')

        def watch_sql(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith(('INSERT INTO USER_GROUPS', 'DELETE FROM USER_GROUPS')):
                events.append('group_write')

        event.listen(db.session(), 'do_orm_execute', watch_orm)
        event.listen(db.engine, 'before_cursor_execute', watch_sql)
        try:
            with patch('app.rbac.services.write_audit_log'), patch('app.rbac.services._invalidate_api_scope_cache'):
                result = set_user_groups(1, [8])
            self.assertTrue(result['ok'], result)
            self.assertIn('group_write', events)
            self.assertLess(events.index('lock'), events.index('group_write'))
        finally:
            event.remove(db.session(), 'do_orm_execute', watch_orm)
            event.remove(db.engine, 'before_cursor_execute', watch_sql)

    def test_missing_bad_and_wrong_subject_tokens_fail_closed(self):
        token = self.token()
        decoded = _serializer().loads(token)
        decoded['actor'] = 2
        for bad in ('', token + 'broken', _serializer().dumps(decoded)):
            with self.subTest(bad=bad[:8]):
                self.assertTrue(self.save(bad, task_keyword='new')['reload_required'])

    def test_snapshot_has_no_secret_values(self):
        self.task.req_url = 'https://example.invalid/?token=SECRET'
        self.task.req_body = '{"password":"SECRET"}'
        db.session.commit()
        decoded = _serializer().loads(self.token())
        self.assertNotIn('SECRET', str(decoded))
        self.assertNotIn('password', str(decoded))

    def test_explicit_resume_is_required_and_pause_is_preserved(self):
        token = self.token()
        self.task.status = 1
        db.session.commit()
        result = self.save(token, task_keyword='edited')
        self.assertEqual(result['outcome'], 'updated')
        self.assertEqual(db.session.get(CronInfos, self.task_id).status, 1)

    def test_retired_task_cannot_be_overwritten(self):
        token = self.token()
        self.task.status = -1
        db.session.commit()
        self.assertEqual(self.save(token, task_keyword='new')['outcome'], 'failed')

    def test_scope_target_requires_current_permission(self):
        token = self.token()
        result = self.save(token, scope_type='GLOBAL', group_id=None)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(list(db.session.scalars(select(TaskGroup.group_id))), [7])

    def test_mapper_cas_detects_write_after_read(self):
        with Session(db.engine) as first, Session(db.engine) as second:
            old = first.get(CronInfos, self.task_id)
            new = second.get(CronInfos, self.task_id)
            new.task_keyword = 'concurrent committed'
            second.commit()
            old.timeout_sec = 10
            with self.assertRaises(StaleDataError):
                first.flush()
            first.rollback()
        db.session.expire_all()
        self.assertEqual(db.session.get(CronInfos, self.task_id).task_keyword, 'concurrent committed')
        self.assertIsNone(db.session.get(CronInfos, self.task_id).timeout_sec)

    def test_stale_write_retries_once_then_reports_conflict(self):
        token = self.token()
        real_flush = db.session.flush
        attempts = []

        def stale_once(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise StaleDataError('injected concurrent write')
            return real_flush(*args, **kwargs)

        with patch.object(db.session, 'flush', side_effect=stale_once):
            self.assertEqual(self.save(token, task_keyword='retry succeeds')['outcome'], 'updated')
        self.assertGreaterEqual(len(attempts), 2)
        token = self.token()
        with patch.object(db.session, 'flush', side_effect=StaleDataError('repeated contention')) as flush:
            self.assertEqual(self.save(token, task_keyword='must not persist')['outcome'], 'conflict')
        self.assertEqual(flush.call_count, 2)
        self.assertEqual(db.session.get(CronInfos, self.task_id).task_keyword, 'retry succeeds')

    def test_orm_status_and_tag_delete_both_advance_revision(self):
        with patch('app.services.cron_service.scheduler'):
            toggle_status(self.task_id, target_status=1)
        db.session.refresh(self.task)
        revision = self.task.edit_revision
        self.assertEqual(revision, 1)
        delete_tag(1, force=True)
        db.session.refresh(self.task)
        self.assertEqual(self.task.edit_revision, revision + 1)

    def test_validation_failure_does_not_rebase_token(self):
        token = self.token()
        self.assertEqual(self.save(token, timeout_sec='invalid')['outcome'], 'failed')
        self.task.task_keyword = 'concurrent'
        db.session.commit()
        self.assertEqual(self.save(token, task_keyword='old retry')['outcome'], 'conflict')

    def test_scheduler_fallback_never_retires_a_newer_revision(self):
        from app.CuBackgroundScheduler import CuBackgroundScheduler
        from app.CuGeventScheduler import CuGeventScheduler

        for scheduler_class in (CuBackgroundScheduler, CuGeventScheduler):
            with self.subTest(scheduler=scheduler_class.__name__):
                instance = object.__new__(scheduler_class)
                instance._logger = logging.getLogger('test.scheduler')

                def concurrent_update_then_failure(task, _reason):
                    task.task_keyword = 'newer committed edit ' + scheduler_class.__name__
                    db.session.commit()
                    raise RuntimeError('simulated primary path failure')

                with patch('app.scheduler', SimpleNamespace(app=self.app)), \
                        patch('app.services.cron_service.apply_retire',
                              side_effect=concurrent_update_then_failure):
                    instance.update_cron_info('cron_%s' % self.task_id)
                db.session.expire_all()
                current = db.session.get(CronInfos, self.task_id)
                self.assertEqual(current.task_keyword, 'newer committed edit ' + scheduler_class.__name__)
                self.assertNotEqual(current.status, -1)


if __name__ == '__main__':
    unittest.main()
