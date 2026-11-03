import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import db
from app.services.cron_edit_apply import EditWriteError, apply_edit
from tests import test_cron_edit_noop as fixture


class TestEditApply(unittest.TestCase):
    setUp = fixture.TestCronEditNoop.setUp
    tearDown = fixture.TestCronEditNoop.tearDown

    def apply(self):
        return apply_edit(self.task_id, self.task.edit_revision, dict(self.values, status=0))

    def test_success_does_not_query_jobstore(self):
        with patch('app.services.cron_edit_apply.scheduler', state=1) as sched, \
                patch('app.services.cron_service.register_cron_job', return_value=SimpleNamespace(pending=False)) as reg:
            self.apply()
            sched.get_job.assert_not_called()
            reg.assert_called_once_with(self.task_id, dict(self.values, status=0), paused=True)

    def test_uncertain_exception_queries_and_accepts_confirmed_target(self):
        with patch('app.services.cron_edit_apply.scheduler', state=1), \
                patch('app.services.cron_service.register_cron_job', side_effect=RuntimeError('lost ack')), \
                patch('app.services.cron_edit_apply.query_target', return_value=True) as query:
            self.apply()
            query.assert_called_once()

    def test_query_mismatch_and_query_failure_are_safe_errors(self):
        for value, message in ((False, '不一致'), (None, '待核实')):
            with self.subTest(value=value), patch('app.services.cron_edit_apply.scheduler', state=1), \
                    patch('app.services.cron_service.register_cron_job', side_effect=RuntimeError('SECRET')), \
                    patch('app.services.cron_edit_apply.query_target', return_value=value):
                with self.assertRaisesRegex(EditWriteError, message) as result:
                    self.apply()
                self.assertNotIn('SECRET', str(result.exception))

    def test_conflict_before_application_stops_write(self):
        with patch('app.services.cron_edit_apply.current_version', return_value=(99, 0)), \
                patch('app.services.cron_service.register_cron_job') as reg:
            with self.assertRaisesRegex(EditWriteError, '后续变更'):
                self.apply()
            reg.assert_not_called()

    def test_conflict_after_normal_return_is_not_scheduler_failure(self):
        def change(*args, **kwargs):
            self.task.task_keyword = 'concurrent'
            db.session.commit()
            return SimpleNamespace(pending=False)
        with patch('app.services.cron_edit_apply.scheduler', state=1) as sched, \
                patch('app.services.cron_service.register_cron_job', side_effect=change):
            with self.assertRaisesRegex(EditWriteError, '后续变更'):
                self.apply()
            sched.get_job.assert_not_called()

    def test_stopped_and_pending_are_not_persistent_success(self):
        with patch('app.services.cron_edit_apply.scheduler', state=0), \
                patch('app.services.cron_service.register_cron_job') as reg:
            with self.assertRaisesRegex(EditWriteError, '未启动'):
                self.apply()
            reg.assert_not_called()
        with patch('app.services.cron_edit_apply.scheduler', state=1), \
                patch('app.services.cron_service.register_cron_job', return_value=SimpleNamespace(pending=True)):
            with self.assertRaisesRegex(EditWriteError, '暂存'):
                self.apply()

    def test_version_query_failure_does_not_claim_unsaved(self):
        with patch('app.services.cron_edit_apply.current_version', side_effect=RuntimeError('connection')), \
                patch('app.services.cron_service.register_cron_job') as reg:
            with self.assertRaisesRegex(EditWriteError, '已保存.*并发核验'):
                self.apply()
            reg.assert_not_called()

    def test_query_exception_preserves_uncertain_result(self):
        with patch('app.services.cron_edit_apply.scheduler', state=1), \
                patch('app.services.cron_service.register_cron_job', side_effect=RuntimeError('lost ack')), \
                patch('app.services.cron_edit_apply.query_target', side_effect=RuntimeError('read failed')):
            with self.assertRaisesRegex(EditWriteError, '待核实'):
                self.apply()

    def test_post_success_read_failure_preserves_known_scheduler_success(self):
        with patch('app.services.cron_edit_apply.current_version',
                   side_effect=[(self.task.edit_revision, 0), RuntimeError('read failed')]), \
                patch('app.services.cron_edit_apply.scheduler', state=1) as sched, \
                patch('app.services.cron_service.register_cron_job', return_value=SimpleNamespace(pending=False)):
            with self.assertRaisesRegex(EditWriteError, '调度调用成功.*并发核验'):
                self.apply()
            sched.get_job.assert_not_called()

    def test_commit_failure_does_not_apply_even_if_target_would_match(self):
        from app.services.cron_service import update_cron_with_outcome
        with patch.object(db.session, 'commit', side_effect=RuntimeError('SECRET')), \
                patch('app.services.cron_service.apply_edit') as apply:
            with self.assertRaisesRegex(EditWriteError, '保存结果待核实'):
                update_cron_with_outcome(self.task, dict(self.values, minute='8'))
            apply.assert_not_called()

    def test_exhausted_connection_pool_fails_safely_without_scheduler_write(self):
        from sqlalchemy import create_engine
        from sqlalchemy.pool import QueuePool

        engine = create_engine('sqlite:///:memory:', poolclass=QueuePool,
                               pool_size=1, max_overflow=0, pool_timeout=0.01)
        original = db.engines[None]
        try:
            with engine.connect(), patch('app.services.cron_service.register_cron_job') as reg:
                db.engines[None] = engine
                with self.assertRaisesRegex(EditWriteError, '已保存.*并发核验'):
                    self.apply()
                reg.assert_not_called()
        finally:
            db.engines[None] = original
            engine.dispose()

    def test_query_missing_and_full_trigger_comparison(self):
        from apscheduler.triggers.cron import CronTrigger

        from app.services.cron_edit_apply import query_target
        from app.services.cron_service import build_scheduler_kwargs

        target = dict(self.values, status=0)
        kwargs = dict(build_scheduler_kwargs(target))
        kwargs.pop('trigger')
        trigger = CronTrigger(timezone='UTC', **kwargs)
        job = SimpleNamespace(id='cron_%s' % self.task_id, func_ref='app.crons:cron_do',
                              args=[self.task_id], kwargs={}, executor='default', trigger=trigger,
                              misfire_grace_time=1, coalesce=True, max_instances=1, next_run_time=None)
        with patch('app.services.cron_edit_apply.scheduler', state=1) as sched:
            sched.scheduler.timezone = 'UTC'
            sched.app.config = {}
            sched.get_job.return_value = job
            self.assertTrue(query_target(self.task_id, target))
            for field, value in (('args', [999]), ('next_run_time', object()), ('max_instances', 2),
                                 ('trigger', CronTrigger(timezone='UTC', second='1'))):
                old = getattr(job, field)
                setattr(job, field, value)
                self.assertFalse(query_target(self.task_id, target), field)
                setattr(job, field, old)
            sched.get_job.return_value = None
            self.assertFalse(query_target(self.task_id, target))
            self.assertIsNone(query_target(self.task_id, dict(target, run_date='2020-01-01 00:00:00')))

    def test_api_upsert_and_legacy_web_preserve_committed_error_message(self):
        from app.services.cron_service import edit_cron_web, upsert_cron_by_task_name
        for action in (
            lambda: upsert_cron_by_task_name(dict(self.values, minute='5', timeout_sec=''), 0, {}),
            lambda: edit_cron_web(dict(self.raw, minute='6'), 0, {}, self.task_id),
        ):
            with patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')), \
                    patch('app.services.cron_service.apply_edit',
                          side_effect=EditWriteError('配置已保存，但任务有后续变更，请刷新核实')):
                result = action()
            self.assertIn('配置已保存', result[0])

    def test_register_paused_supplies_none_in_single_call(self):
        from app.services.cron_service import register_cron_job
        with patch('app.services.cron_service.scheduler') as sched:
            register_cron_job(self.task_id, self.values, paused=True)
            self.assertIsNone(sched.add_job.call_args.kwargs['next_run_time'])
            sched.pause_job.assert_not_called()

    def test_real_sqlalchemy_jobstore_success_and_lost_ack(self):
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        from apscheduler.schedulers.background import BackgroundScheduler
        from flask_apscheduler import APScheduler

        defaults = dict(coalesce=False, max_instances=20, misfire_grace_time=50)
        base = BackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url='sqlite:///:memory:')},
                                   job_defaults=defaults, timezone='UTC')
        api = APScheduler(scheduler=base)
        api.app = SimpleNamespace(config={'SCHEDULER_JOB_DEFAULTS': defaults})
        base.start(paused=True)
        try:
            with patch('app.services.cron_edit_apply.scheduler', api), \
                    patch('app.services.cron_service.scheduler', api):
                with patch.object(api, 'get_job', side_effect=AssertionError('normal path queried')):
                    self.apply()
                self.assertIsNone(api.get_job('cron_%s' % self.task_id).next_run_time)
                store = base._jobstores['default']
                update = store.update_job

                def lost_ack(job):
                    update(job)
                    raise RuntimeError('applied but acknowledgement lost')

                with patch.object(store, 'update_job', side_effect=lost_ack), \
                        patch.object(api, 'get_job', wraps=api.get_job) as query:
                    self.apply()
                    query.assert_called_once()
                from app.services.cron_edit_apply import query_target
                for status in (0, 1):
                    self.task.status = status
                    db.session.commit()
                    target = dict(self.values, status=status, run_date='2100-01-01 00:00:00')
                    apply_edit(self.task_id, self.task.edit_revision, target)
                    self.assertTrue(query_target(self.task_id, target))
                    self.assertEqual(api.get_job('cron_%s' % self.task_id).next_run_time is None, status == 0)
                # 成功返回之后的其他写入不在本次有限检测窗口内；本方案不提供 fencing。
                from app.services.cron_service import register_cron_job
                register_cron_job(self.task_id, self.values)
                self.assertFalse(query_target(self.task_id, target))
        finally:
            base.shutdown(wait=True)
