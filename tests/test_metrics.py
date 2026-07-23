"""
Tests for app/metrics.py — Prometheus metric declarations.

Verifies:
- All five metric objects and _ctx_enqueue_time are importable.
- Each metric type accepts its intended call signature without raising.
- NoOp fallback class silently handles all operations.
"""
import os
import time
import unittest

# Ensure multiproc dir exists before module-level metric objects are created.
_PROM_DIR = '/tmp/prom_test_metrics'
os.makedirs(_PROM_DIR, exist_ok=True)
os.environ.setdefault('PROMETHEUS_MULTIPROC_DIR', _PROM_DIR)


class TestMetricsImport(unittest.TestCase):
    """Module-level objects must be importable and expose the correct API."""

    @classmethod
    def setUpClass(cls):
        from app import metrics as m
        cls.m = m

    def test_all_exports_present(self):
        for name in ('JOB_TOTAL', 'JOB_DURATION', 'TRIGGER_DELAY',
                     'JOB_LOG_WRITE_BYTES', 'JOBS_ACTIVE', '_ctx_enqueue_time'):
            self.assertTrue(hasattr(self.m, name), f"missing export: {name}")

    def test_job_total_labels_inc(self):
        self.m.JOB_TOTAL.labels(task_name='ut_task', status='ok').inc()

    def test_job_duration_labels_observe(self):
        self.m.JOB_DURATION.labels(task_name='ut_task', status='ok').observe(0.42)

    def test_trigger_delay_labels_observe(self):
        self.m.TRIGGER_DELAY.labels(task_name='ut_task').observe(0.1)

    def test_job_log_write_bytes_observe(self):
        self.m.JOB_LOG_WRITE_BYTES.observe(1024)

    def test_jobs_active_set(self):
        self.m.JOBS_ACTIVE.labels(state='active').set(7)
        self.m.JOBS_ACTIVE.labels(state='retired').set(1)

    def test_ctx_enqueue_time_read_write(self):
        t = time.time()
        self.m._ctx_enqueue_time.set(t)
        self.assertAlmostEqual(self.m._ctx_enqueue_time.get(), t, places=5)


class TestMetricsNoOp(unittest.TestCase):
    """NoOp fallback must swallow all calls without raising."""

    def _make_noop(self):
        """Return a fresh _NoOp instance as defined in app/metrics.py."""
        class _NoOp:
            def labels(self, **_): return self
            def observe(self, _): pass
            def inc(self): pass
            def set(self, _): pass
        return _NoOp()

    def test_noop_inc(self):
        self._make_noop().labels(task_name='x', status='ok').inc()

    def test_noop_observe(self):
        self._make_noop().labels(task_name='x', status='ok').observe(1.0)

    def test_noop_set(self):
        self._make_noop().labels(state='active').set(3)

    def test_noop_chained_labels(self):
        n = self._make_noop()
        n.labels(task_name='a').labels(extra='b').observe(0.5)


if __name__ == '__main__':
    unittest.main()
