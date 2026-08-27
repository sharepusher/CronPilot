# -*- coding:utf-8 -*-
"""Unit tests for _compute_overdue_map() overdue detection logic."""
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.main.views import _compute_overdue_map


def _task(tid, status=1, minute='0', hour='*', day='*', dow='*', run_date=''):
    return SimpleNamespace(
        id=tid, status=status, minute=minute, hour=hour,
        day=day, day_of_week=dow, run_date=run_date,
    )


class TestComputeOverdueMap(unittest.TestCase):

    def test_overdue_when_interval_exceeded(self):
        """Task last ran > 2x interval ago → overdue."""
        task = _task(1, minute='0')
        now = datetime.now()
        last = (now - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertIn(1, result)
        self.assertTrue(result[1].startswith('逾期'))

    def test_not_overdue_within_interval(self):
        """Task last ran within 2x interval → not overdue."""
        task = _task(1, minute='0')
        now = datetime.now()
        last = (now - timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertNotIn(1, result)

    def test_paused_task_not_overdue(self):
        """Paused task (status=0) → excluded from overdue."""
        task = _task(1, status=0, minute='0')
        now = datetime.now()
        last = (now - timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertNotIn(1, result)

    def test_retired_task_not_overdue(self):
        """Retired task (status=-1) → excluded from overdue."""
        task = _task(1, status=-1, minute='0')
        now = datetime.now()
        last = (now - timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertNotIn(1, result)

    def test_one_shot_task_not_overdue(self):
        """One-shot task (run_date set) → excluded from overdue."""
        task = _task(1, run_date='2026-08-15 10:00:00', minute='0')
        now = datetime.now()
        last = (now - timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertNotIn(1, result)

    def test_no_exec_history_not_overdue(self):
        """Task with no execution history → not marked overdue."""
        task = _task(1, minute='0')
        result = _compute_overdue_map([task], {})
        self.assertNotIn(1, result)

    def test_overdue_duration_format_hours(self):
        """Overdue duration formats as hours for < 24h."""
        task = _task(1, minute='0')
        now = datetime.now()
        last = (now - timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertIn(1, result)
        self.assertIn('h', result[1])

    def test_overdue_duration_format_days(self):
        """Overdue duration formats as days for >= 24h."""
        task = _task(1, minute='0')
        now = datetime.now()
        last = (now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertIn(1, result)
        self.assertIn('d', result[1])

    def test_minimum_threshold_10min(self):
        """Even for high-frequency tasks, threshold is at least 10 minutes."""
        task = _task(1, minute='*/2')
        now = datetime.now()
        last = (now - timedelta(minutes=8)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertNotIn(1, result)

    def test_minimum_threshold_triggers_at_11min(self):
        """High-frequency task overdue after exceeding 10min threshold."""
        task = _task(1, minute='*/2')
        now = datetime.now()
        last = (now - timedelta(minutes=11)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertIn(1, result)

    def test_wildcard_only_cron_skipped(self):
        """Task with '* * * * *' cron expression is skipped."""
        task = _task(1, minute='*', hour='*', day='*', dow='*')
        now = datetime.now()
        last = (now - timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S')
        result = _compute_overdue_map([task], {1: last})
        self.assertNotIn(1, result)

    def test_multiple_tasks_mixed(self):
        """Multiple tasks: only overdue ones appear in result."""
        t1 = _task(1, minute='0')
        t2 = _task(2, minute='30')
        now = datetime.now()
        last_map = {
            1: (now - timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S'),
            2: (now - timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S'),
        }
        result = _compute_overdue_map([t1, t2], last_map)
        self.assertIn(1, result)
        self.assertNotIn(2, result)


if __name__ == '__main__':
    unittest.main()
