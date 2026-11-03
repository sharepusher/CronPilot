"""日志故障不能反向撤销已完成的真实调度操作。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from flask_apscheduler import APScheduler

from app import db
from app.crons import cron_do
from app.services.cron_service import toggle_status
from tests import test_cron_edit_noop as fixture


class TestStatusLoggingD2(unittest.TestCase):
    setUp = fixture.TestCronEditNoop.setUp
    tearDown = fixture.TestCronEditNoop.tearDown

    def test_successful_pause_survives_success_log_failure(self):
        self.task.status = 1
        db.session.commit()
        with tempfile.TemporaryDirectory(prefix='cron-status-jobstore-') as directory:
            store = SQLAlchemyJobStore(url='sqlite:///' + str(Path(directory) / 'jobs.sqlite'))
            base = BackgroundScheduler(jobstores={'default': store})
            api = APScheduler(scheduler=base)
            api.app = SimpleNamespace(config={})
            base.start(paused=True)
            try:
                job_id = 'cron_%s' % self.task_id
                base.add_job(cron_do, 'cron', id=job_id, args=[self.task_id], hour='23', minute='59')
                with patch('app.services.cron_status_apply.scheduler', api), \
                        patch('app.services.cron_status_apply.logger.info', side_effect=RuntimeError('log failure')):
                    result = toggle_status(self.task_id, target_status=0)
                db.session.refresh(self.task)
                self.assertTrue(result[0], result)
                self.assertEqual(self.task.status, 0)
                self.assertIsNone(base.get_job(job_id).next_run_time)
            finally:
                base.shutdown(wait=True)
