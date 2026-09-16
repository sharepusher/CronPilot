# -*- coding:utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.services.cron_schedule_display import (
    cron_trigger_from_item,
    format_cron_expression,
    humanize_schedule,
    schedule_empty_hint,
)


class _Item(object):
    def __init__(self, **kwargs):
        self.run_date = kwargs.get('run_date', '')
        self.day_of_week = kwargs.get('day_of_week', '')
        self.day = kwargs.get('day', '')
        self.hour = kwargs.get('hour', '')
        self.minute = kwargs.get('minute', '')
        self.second = kwargs.get('second', '')


class TestCronScheduleDisplay(unittest.TestCase):
    def test_every_five_minutes(self):
        item = _Item(minute='*/5')
        self.assertEqual(humanize_schedule(item), '每 5 分钟')
        self.assertIn('*/5', format_cron_expression(item))

    def test_seconds_expression_is_preserved(self):
        item = _Item(second='*/10', minute='*', hour='*')
        self.assertEqual(format_cron_expression(item), '*/10 * * * * *')

    def test_explicit_second_is_preserved_with_period(self):
        item = _Item(second='5', minute='*/5')
        self.assertEqual(format_cron_expression(item), '5 */5 * * * *')

    def test_hour_only_shows_minute_zero_not_star(self):
        item = _Item(hour='*/2')
        self.assertEqual(format_cron_expression(item), '0 */2 * * *')
        self.assertEqual(humanize_schedule(item), '每 2 小时 的第 0 分')

    def test_weekly_tuesday(self):
        item = _Item(day_of_week='tue', hour='2', minute='0')
        self.assertEqual(humanize_schedule(item), '每周二 02:00')

    def test_daily(self):
        item = _Item(hour='8', minute='30')
        self.assertEqual(humanize_schedule(item), '每天 08:30')

    def test_one_shot(self):
        item = _Item(run_date='2026-07-16 10:00')
        self.assertEqual(humanize_schedule(item), '一次性 2026-07-16 10:00')
        self.assertEqual(format_cron_expression(item), '')

    def test_empty_schedule(self):
        item = _Item()
        self.assertIsNone(cron_trigger_from_item(item))
        self.assertEqual(humanize_schedule(item), '未配置调度')
        self.assertEqual(format_cron_expression(item), '')

    def test_schedule_empty_hint_skips_paused_and_retired(self):
        item = _Item(hour='9')
        self.assertEqual(schedule_empty_hint(item, status=0), '')
        self.assertEqual(schedule_empty_hint(item, status=-1), '')
        self.assertEqual(schedule_empty_hint(item, status=1), '等待首次触发')
        empty = _Item()
        self.assertEqual(schedule_empty_hint(empty, status=1), '调度未配置，不会自动执行')


if __name__ == '__main__':
    unittest.main()
