# -*- coding: utf-8 -*-
"""
Prometheus metric declarations for CronPilot.

All metrics are declared here to avoid duplicate-registration errors across
modules (prometheus_client raises ValueError on double-register).

A NoOp fallback is provided so the rest of the codebase can import from here
unconditionally without guarding every call site with try/except.
"""
import os
from contextvars import ContextVar

# Enqueue timestamp written by single_task decorator; read by cron_do to compute trigger delay.
_ctx_enqueue_time: ContextVar[float] = ContextVar('enqueue_time', default=0.0)

try:
    from prometheus_client import Counter, Histogram, Gauge

    # ------------------------------------------------------------------ #
    # Job execution metrics                                                #
    # ------------------------------------------------------------------ #
    JOB_TOTAL = Counter(
        'cronpilot_job_total',
        'Total job executions',
        ['task_name', 'status'],
    )

    JOB_DURATION = Histogram(
        'cronpilot_job_duration_seconds',
        'HTTP callback duration per execution',
        ['task_name', 'status'],
        buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120, float('inf')],
    )

    # Scheduling latency: enqueue-to-actual-start wall time
    # Set via _ctx_enqueue_time ContextVar in single_task decorator.
    TRIGGER_DELAY = Histogram(
        'cronpilot_job_trigger_delay_seconds',
        'Wall-clock delay between task enqueue and execution start',
        ['task_name'],
        buckets=[0.05, 0.1, 0.5, 1, 5, 15, 30, 60, float('inf')],
    )

    # Content size distribution — used to calibrate large-body split threshold
    JOB_LOG_WRITE_BYTES = Histogram(
        'cronpilot_job_log_write_bytes',
        'Bytes written per job_log.content field',
        buckets=[1024, 4096, 16384, 32768, 65536, 131072, 524288, 2097152, float('inf')],
    )

    # ------------------------------------------------------------------ #
    # Scheduler state gauge (updated by cron_check every 30 min)          #
    # ------------------------------------------------------------------ #
    JOBS_ACTIVE = Gauge(
        'cronpilot_jobs_active',
        'Current job count by state',
        ['state'],
    )

    _PROMETHEUS_AVAILABLE = True

except ImportError:
    _PROMETHEUS_AVAILABLE = False

    class _NoOp:
        """Silent no-op when prometheus_client is not installed."""
        def labels(self, **_): return self
        def observe(self, _): pass
        def inc(self): pass
        def set(self, _): pass

    _noop = _NoOp()
    JOB_TOTAL = JOB_DURATION = TRIGGER_DELAY = JOB_LOG_WRITE_BYTES = JOBS_ACTIVE = _noop
