# -*- coding: utf-8 -*-
"""Threadpool executor that carries the scheduled fire time into cron_do."""
from apscheduler.executors.base import run_job
from apscheduler.executors.pool import ThreadPoolExecutor

from app.metrics import _ctx_scheduled_run_time


class ContextThreadPoolExecutor(ThreadPoolExecutor):
    def _do_submit_job(self, job, run_times):
        planned_run_time = run_times[-1] if run_times else None

        def run_with_context():
            token = _ctx_scheduled_run_time.set(planned_run_time)
            try:
                return run_job(job, job._jobstore_alias, run_times, self._logger.name)
            finally:
                _ctx_scheduled_run_time.reset(token)

        def callback(future):
            exc = future.exception()
            if exc:
                self._run_job_error(job.id, exc, exc.__traceback__)
            else:
                self._run_job_success(job.id, future.result())

        future = self._pool.submit(run_with_context)
        future.add_done_callback(callback)
