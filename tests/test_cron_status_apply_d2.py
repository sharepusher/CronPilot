"""真实 JobStore 下验证启停结果、同目标重试和版本冲突。"""
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from flask_apscheduler import APScheduler

from app import db
from app.crons import cron_do
from app.services.cron_status_apply import save_status
from tests import test_cron_edit_noop as fixture


class TestStatusApplyD2(unittest.TestCase):
    setUp = fixture.TestCronEditNoop.setUp
    tearDown = fixture.TestCronEditNoop.tearDown

    @contextmanager
    def scheduler(self):
        with tempfile.TemporaryDirectory() as directory:
            base = BackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(
                url='sqlite:///' + str(Path(directory) / 'jobs.sqlite'))})
            api = APScheduler(scheduler=base)
            api.app = SimpleNamespace(config={})
            base.start(paused=True)
            base.add_job(cron_do, 'cron', id='cron_%s' % self.task_id,
                         args=[self.task_id], hour='1', minute='0', next_run_time=None)
            try:
                with patch('app.services.cron_status_apply.scheduler', api), \
                        patch('app.services.cron_edit_apply.scheduler', api):
                    yield api
            finally:
                base.shutdown(wait=True)

    def test_normal_success_has_no_jobstore_query(self):
        with self.scheduler() as api, patch.object(api, 'get_job', side_effect=AssertionError('unexpected read')):
            self.assertTrue(save_status(self.task_id, 1)[0])

    def test_uncertain_failure_preserves_target_and_retry_applies(self):
        with self.scheduler() as api:
            with patch.object(api.scheduler, 'resume_job', side_effect=RuntimeError('SECRET')):
                result = save_status(self.task_id, 1)
            self.assertFalse(result[0])
            self.assertNotIn('SECRET', result[1])
            db.session.refresh(self.task)
            self.assertEqual(self.task.status, 1)
            version = self.task.edit_revision
            self.assertTrue(save_status(self.task_id, 1, expected_revision=version)[0])
            next_run = api.get_job('cron_%s' % self.task_id).next_run_time
            with patch.object(api.scheduler, 'resume_job', side_effect=AssertionError('duplicate resume')):
                self.assertTrue(save_status(self.task_id, 1, expected_revision=version)[0])
            self.assertEqual(api.get_job('cron_%s' % self.task_id).next_run_time, next_run)

    def test_stale_retry_cannot_override_later_change(self):
        with self.scheduler() as api:
            self.assertTrue(save_status(self.task_id, 1)[0])
            db.session.refresh(self.task)
            old_version = self.task.edit_revision
            self.assertTrue(save_status(self.task_id, 0)[0])
            with patch.object(api.scheduler, 'resume_job') as resume:
                self.assertFalse(save_status(self.task_id, 1, expected_revision=old_version)[0])
                resume.assert_not_called()

    def test_applied_then_exception_is_observed_without_compensation(self):
        with self.scheduler() as api:
            store = api.scheduler._jobstores['default']
            update = store.update_job
            def applied_then_raise(job):
                update(job)
                raise RuntimeError('lost acknowledgement')
            with patch.object(store, 'update_job', side_effect=applied_then_raise):
                self.assertTrue(save_status(self.task_id, 1)[0])
            db.session.refresh(self.task)
            self.assertEqual(self.task.status, 1)

    def test_noop_releases_authorization_transaction(self):
        self.sql.clear()
        self.assertTrue(save_status(self.task_id, 0, actor_id=1)[0])
        self.assertFalse(db.session().in_transaction())
        self.assertFalse(self.sql)

    def test_invalid_targets_do_not_write(self):
        for value in (True, False, 2, 'bad', ''):
            self.sql.clear()
            self.assertFalse(save_status(self.task_id, value)[0])
            self.assertFalse(self.sql)
