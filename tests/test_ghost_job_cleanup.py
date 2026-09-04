# -*- coding:utf-8 -*-
"""Tests for OPT-P0-20: ghost job cleanup and retire flow hardening."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from flask import Flask

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)


def _make_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['CRONPILOT_SCHEDULER_ENABLED'] = False
    app.config['CRON_DB_URL'] = ''
    return app


class _FakeCif:
    """Lightweight stand-in for CronInfos."""
    def __init__(self, id, task_name='', status=1, retire_reason=None, retired_at=None):
        self.id = id
        self.task_name = task_name
        self.status = status
        self.retire_reason = retire_reason
        self.retired_at = retired_at


# ═══════════════════════════════════════════════════════════════════════
# Batch 1: retire flow hardening
# ═══════════════════════════════════════════════════════════════════════

class TestRetireFlowHardened(unittest.TestCase):
    """Tests for retire_cron_by_id with remove_job-first ordering."""

    def setUp(self):
        self.app = _make_app()
        self.app_ctx = self.app.app_context()
        self.app_ctx.push()

    def tearDown(self):
        self.app_ctx.pop()

    @patch('app.services.cron_service._record_retire')
    @patch('app.services.cron_service.apply_retire')
    @patch('app.services.cron_service.scheduler')
    @patch('app.services.cron_service.db')
    def test_retire_normal_success(self, mock_db, mock_sched, mock_apply, mock_record):
        cif = _FakeCif(id=1, task_name='test_task', status=1)
        mock_db.session.get.return_value = cif
        mock_sched.remove_job.return_value = None

        from app.services.cron_service import retire_cron_by_id
        err, result = retire_cron_by_id(1, '手动下线')

        self.assertIsNone(err)
        mock_sched.remove_job.assert_called_once_with('cron_1')
        mock_apply.assert_called_once()
        mock_db.session.commit.assert_called_once()

    @patch('app.services.cron_service._record_retire')
    @patch('app.services.cron_service.apply_retire')
    @patch('app.services.cron_service.scheduler')
    @patch('app.services.cron_service.db')
    def test_retire_job_already_absent(self, mock_db, mock_sched, mock_apply, mock_record):
        """JobLookupError should be treated as idempotent — retire succeeds."""
        from apscheduler.jobstores.base import JobLookupError
        cif = _FakeCif(id=2, task_name='test_absent', status=1)
        mock_db.session.get.return_value = cif
        mock_sched.remove_job.side_effect = JobLookupError('cron_2')

        from app.services.cron_service import retire_cron_by_id
        err, result = retire_cron_by_id(2, '手动下线')

        self.assertIsNone(err)
        mock_apply.assert_called_once()
        mock_db.session.commit.assert_called_once()

    @patch('app.services.cron_service._record_retire')
    @patch('app.services.cron_service.apply_retire')
    @patch('app.services.cron_service.scheduler')
    @patch('app.services.cron_service.db')
    def test_retire_remove_job_fails(self, mock_db, mock_sched, mock_apply, mock_record):
        """Other exceptions should abort the retire — status must NOT change."""
        cif = _FakeCif(id=3, task_name='test_fail', status=1)
        mock_db.session.get.return_value = cif
        mock_sched.remove_job.side_effect = RuntimeError('DB lock timeout')

        from app.services.cron_service import retire_cron_by_id
        err, result = retire_cron_by_id(3, '手动下线')

        self.assertIsNotNone(err)
        self.assertIn('调度器移除失败', err)
        mock_apply.assert_not_called()
        mock_db.session.commit.assert_not_called()


class TestRetireByTaskNameHardened(unittest.TestCase):
    """Tests for retire_cron_by_task_name with remove_job-first ordering."""

    def setUp(self):
        self.app = _make_app()
        self.app_ctx = self.app.app_context()
        self.app_ctx.push()

    def tearDown(self):
        self.app_ctx.pop()

    @patch('app.services.cron_service._record_retire')
    @patch('app.services.cron_service.apply_retire')
    @patch('app.services.cron_service.scheduler')
    @patch('app.services.cron_service.db')
    def test_by_name_normal_success(self, mock_db, mock_sched, mock_apply, mock_record):
        cif = _FakeCif(id=10, task_name='by_name_task', status=1)
        mock_db.session.scalars.return_value.first.return_value = cif

        from app.services.cron_service import retire_cron_by_task_name
        err, result = retire_cron_by_task_name('by_name_task', '手动下线')

        self.assertIsNone(err)
        mock_sched.remove_job.assert_called_once_with('cron_10')
        mock_apply.assert_called_once()

    @patch('app.services.cron_service._record_retire')
    @patch('app.services.cron_service.apply_retire')
    @patch('app.services.cron_service.scheduler')
    @patch('app.services.cron_service.db')
    def test_by_name_remove_job_fails(self, mock_db, mock_sched, mock_apply, mock_record):
        cif = _FakeCif(id=11, task_name='by_name_fail', status=1)
        mock_db.session.scalars.return_value.first.return_value = cif
        mock_sched.remove_job.side_effect = RuntimeError('DB lock')

        from app.services.cron_service import retire_cron_by_task_name
        err, result = retire_cron_by_task_name('by_name_fail', '手动下线')

        self.assertIsNotNone(err)
        self.assertIn('调度器移除失败', err)
        mock_apply.assert_not_called()

    @patch('app.services.cron_service._record_retire')
    @patch('app.services.cron_service.apply_retire')
    @patch('app.services.cron_service.scheduler')
    @patch('app.services.cron_service.db')
    def test_by_name_job_lookup_error(self, mock_db, mock_sched, mock_apply, mock_record):
        from apscheduler.jobstores.base import JobLookupError
        cif = _FakeCif(id=12, task_name='by_name_absent', status=1)
        mock_db.session.scalars.return_value.first.return_value = cif
        mock_sched.remove_job.side_effect = JobLookupError('cron_12')

        from app.services.cron_service import retire_cron_by_task_name
        err, result = retire_cron_by_task_name('by_name_absent', '手动下线')

        self.assertIsNone(err)
        mock_apply.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# Batch 2: cron_check reverse scan
# ═══════════════════════════════════════════════════════════════════════

class TestCronCheckReverseScan(unittest.TestCase):
    """Tests for cron_check() reverse ghost job detection."""

    def setUp(self):
        self.app = _make_app()
        self.app_ctx = self.app.app_context()
        self.app_ctx.push()

    def tearDown(self):
        self.app_ctx.pop()

    @patch('app.crons.GHOST_TASKS')
    @patch('app.crons.ORPHAN_TASKS')
    @patch('app.crons.JOBS_ACTIVE')
    @patch('app.crons.scheduler')
    @patch('app.crons.db')
    @patch('app.crons.fetch_apscheduler_job_ids')
    def test_ghost_retired_cleaned(self, mock_fetch, mock_db, mock_sched, mock_active, mock_orphan, mock_ghost):
        """status=-1 task in scheduler should be removed."""
        mock_fetch.return_value = {'cron_1', 'cron_5'}
        mock_sched.app = self.app

        cif_active = _FakeCif(id=1, task_name='active_task', status=1)
        cif_retired = _FakeCif(id=5, task_name='retired_task', status=-1)
        mock_db.session.scalars.return_value.all.return_value = [cif_active, cif_retired]

        from app.crons import cron_check
        cron_check()

        mock_sched.remove_job.assert_called_once_with('cron_5')
        mock_ghost.set.assert_called_once_with(1)

    @patch('app.crons.GHOST_TASKS')
    @patch('app.crons.ORPHAN_TASKS')
    @patch('app.crons.JOBS_ACTIVE')
    @patch('app.crons.scheduler')
    @patch('app.crons.db')
    @patch('app.crons.fetch_apscheduler_job_ids')
    def test_stale_job_only_warns(self, mock_fetch, mock_db, mock_sched, mock_active, mock_orphan, mock_ghost):
        """Job in scheduler with no cron_infos record should only log, NOT remove."""
        mock_fetch.return_value = {'cron_1', 'cron_99'}
        mock_sched.app = self.app

        cif_active = _FakeCif(id=1, task_name='active_task', status=1)
        mock_db.session.scalars.return_value.all.return_value = [cif_active]

        from app.crons import cron_check
        cron_check()

        mock_sched.remove_job.assert_not_called()
        mock_ghost.set.assert_called_once_with(1)

    @patch('app.crons.GHOST_TASKS')
    @patch('app.crons.ORPHAN_TASKS')
    @patch('app.crons.JOBS_ACTIVE')
    @patch('app.crons.scheduler')
    @patch('app.crons.db')
    @patch('app.crons.fetch_apscheduler_job_ids')
    def test_active_job_untouched(self, mock_fetch, mock_db, mock_sched, mock_active, mock_orphan, mock_ghost):
        """Active job (status=1) should not be removed."""
        mock_fetch.return_value = {'cron_1'}
        mock_sched.app = self.app

        cif_active = _FakeCif(id=1, task_name='active_task', status=1)
        mock_db.session.scalars.return_value.all.return_value = [cif_active]

        from app.crons import cron_check
        cron_check()

        mock_sched.remove_job.assert_not_called()
        mock_ghost.set.assert_called_once_with(0)

    @patch('app.crons.GHOST_TASKS')
    @patch('app.crons.ORPHAN_TASKS')
    @patch('app.crons.JOBS_ACTIVE')
    @patch('app.crons.scheduler')
    @patch('app.crons.db')
    @patch('app.crons.fetch_apscheduler_job_ids')
    def test_paused_job_untouched(self, mock_fetch, mock_db, mock_sched, mock_active, mock_orphan, mock_ghost):
        """Paused job (status=0) should not be removed."""
        mock_fetch.return_value = {'cron_2'}
        mock_sched.app = self.app

        cif_paused = _FakeCif(id=2, task_name='paused_task', status=0)
        mock_db.session.scalars.return_value.all.return_value = [cif_paused]

        from app.crons import cron_check
        cron_check()

        mock_sched.remove_job.assert_not_called()
        mock_ghost.set.assert_called_once_with(0)


if __name__ == '__main__':
    unittest.main()
