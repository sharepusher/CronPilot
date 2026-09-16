# -*- coding:utf-8 -*-
"""下次执行 / 有效 crontab 与 APScheduler CronTrigger 对齐。"""
import os
import sys
import unittest
from datetime import datetime
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apscheduler.triggers.cron import CronTrigger

from app.services.cron_schedule_display import (
    cron_fire_interval_seconds,
    effective_crontab_5,
    format_cron_expression,
    next_fire_datetime,
    scheduler_cron_kwargs_from_item,
)
from app.services.dashboard_service import DashboardService


class _Item(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 1)
        self.status = kwargs.get('status', 1)
        self.run_date = kwargs.get('run_date', '')
        self.day_of_week = kwargs.get('day_of_week', '')
        self.day = kwargs.get('day', '')
        self.hour = kwargs.get('hour', '')
        self.minute = kwargs.get('minute', '')
        self.second = kwargs.get('second', '')


class TestEffectiveCronAlignedWithApscheduler(unittest.TestCase):
    def test_empty_minute_with_hour_star_slash_2(self):
        item = _Item(hour='*/2')
        expr = effective_crontab_5(item)
        self.assertTrue(expr.startswith('0 */2'), expr)
        self.assertEqual(format_cron_expression(item), '0 */2 * * *')

    def test_minute_only_star_slash_2(self):
        item = _Item(minute='*/2')
        self.assertEqual(effective_crontab_5(item), '*/2 * * * *')
        self.assertIn('*/2', format_cron_expression(item))

    def test_next_fire_matches_cron_trigger(self):
        item = _Item(hour='*/2')
        now = datetime(2026, 9, 16, 10, 16, 0)
        got = next_fire_datetime(item, now=now)
        kw = scheduler_cron_kwargs_from_item(item)
        trigger = CronTrigger(**{k: v for k, v in kw.items() if k != 'trigger'})
        expect = trigger.get_next_fire_time(None, now)
        self.assertIsNotNone(got)
        self.assertIsNotNone(expect)
        self.assertEqual(
            got.replace(microsecond=0),
            expect.astimezone().replace(tzinfo=None, microsecond=0),
        )

    def test_hour_only_next_not_under_one_minute(self):
        item = _Item(id=14, hour='*/2')
        now = datetime(2026, 9, 16, 10, 16, 0)
        svc = DashboardService(object())
        label = svc.compute_next_runs([item])[14]
        self.assertNotEqual(label, 'in <1 min', label)
        self.assertTrue(label.startswith('in '), label)
        # At 10:16, next even hour :00 is 12:00 → about 1h
        self.assertIn('h', label)

    def test_interval_for_hour_star_slash_2_is_two_hours(self):
        item = _Item(hour='*/2')
        now = datetime(2026, 9, 16, 10, 16, 0)
        sec = cron_fire_interval_seconds(item, now=now)
        self.assertEqual(sec, 7200.0)

    def test_overdue_threshold_uses_two_hour_interval(self):
        """hour=*/2 空 minute：间隔 2h，阈值 4h；3h 前执行不应逾期。"""
        item = _Item(id=1, hour='*/2')
        now = datetime.now()
        from datetime import timedelta
        last = (now - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
        svc = DashboardService(object())
        result = svc.compute_overdue_map([item], {1: last})
        self.assertNotIn(1, result)


if __name__ == '__main__':
    unittest.main()
