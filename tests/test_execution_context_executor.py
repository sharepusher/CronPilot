# -*- coding: utf-8 -*-
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.execution_context_executor import ContextThreadPoolExecutor
from app.metrics import _ctx_scheduled_run_time


class _DoneFuture:
    def __init__(self, result):
        self._result = result

    def exception(self):
        return None

    def result(self):
        return self._result

    def add_done_callback(self, callback):
        callback(self)


class _InlinePool:
    def submit(self, func):
        return _DoneFuture(func())


class TestContextThreadPoolExecutor(unittest.TestCase):
    def test_passes_current_run_time_to_worker_only(self):
        planned = datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc)
        executor = object.__new__(ContextThreadPoolExecutor)
        executor._pool = _InlinePool()
        executor._logger = SimpleNamespace(name='test.executor')
        executor._run_job_success = lambda job_id, events: None
        executor._run_job_error = lambda job_id, exc, tb: self.fail(str(exc))
        job = SimpleNamespace(id='cron_9', _jobstore_alias='default')
        seen = []

        def fake_run_job(*_args):
            seen.append(_ctx_scheduled_run_time.get())
            return []

        with patch('app.execution_context_executor.run_job', side_effect=fake_run_job):
            executor._do_submit_job(job, [planned])

        self.assertEqual(seen, [planned])
        self.assertIsNone(_ctx_scheduled_run_time.get())
