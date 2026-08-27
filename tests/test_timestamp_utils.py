# -*- coding: utf-8 -*-
"""tests/test_timestamp_utils.py — datas/utils/times.py 百毫秒 BIGINT 工具函数测试。

覆盖范围：
  - utc_now_hms 精度与单调性
  - str_to_hms / hms_to_str 互转正确性
  - 空值 / 非法值处理
  - 跨日 / 跨月 / 跨年 / 闰年边界
  - datetime_to_hms / hms_to_datetime 往返
  - local_today_start_hms / local_tomorrow_start_hms 范围
  - date_str_to_hms_range 范围
  - hms_to_display 展示格式
"""
import time
import unittest
from datetime import datetime, timedelta, timezone

from datas.utils.times import (
    utc_now_hms,
    utc_today_start_hms,
    utc_tomorrow_start_hms,
    local_today_start_hms,
    local_tomorrow_start_hms,
    datetime_to_hms,
    hms_to_display,
    hms_to_datetime,
    hms_to_str,
    hms_to_date_str,
    str_to_hms,
    date_str_to_hms_range,
    get_now_time,
    get_today,
)

UTC = timezone.utc


class TestUtcNowHms(unittest.TestCase):
    def test_returns_int(self):
        v = utc_now_hms()
        self.assertIsInstance(v, int)

    def test_precision_is_hectomillisecond(self):
        v = utc_now_hms()
        expected = int(time.time() * 10)
        self.assertAlmostEqual(v, expected, delta=2)

    def test_monotonically_increasing(self):
        v1 = utc_now_hms()
        time.sleep(0.15)
        v2 = utc_now_hms()
        self.assertGreater(v2, v1)

    def test_value_range(self):
        v = utc_now_hms()
        self.assertGreater(v, 17_000_000_000)
        self.assertLess(v, 30_000_000_000)


class TestStrToHms(unittest.TestCase):
    def test_valid_datetime_string(self):
        hms = str_to_hms('2026-08-26 09:55:00')
        self.assertIsNotNone(hms)
        self.assertIsInstance(hms, int)

    def test_roundtrip_str_to_hms_to_str(self):
        original = '2026-08-26 09:55:00'
        hms = str_to_hms(original)
        restored = hms_to_str(hms)
        self.assertEqual(restored, original)

    def test_empty_string_returns_none(self):
        self.assertIsNone(str_to_hms(''))

    def test_none_returns_none(self):
        self.assertIsNone(str_to_hms(None))

    def test_whitespace_returns_none(self):
        self.assertIsNone(str_to_hms('   '))

    def test_invalid_format_returns_none(self):
        self.assertIsNone(str_to_hms('not-a-date'))

    def test_truncates_to_19_chars(self):
        hms = str_to_hms('2026-08-26 09:55:00.12345')
        expected = str_to_hms('2026-08-26 09:55:00')
        self.assertEqual(hms, expected)

    def test_epoch_zero(self):
        hms = str_to_hms('1970-01-01 08:00:00')
        self.assertIsNotNone(hms)


class TestHmsToDisplay(unittest.TestCase):
    def test_basic_display(self):
        hms = str_to_hms('2026-08-26 09:55:00')
        result = hms_to_display(hms)
        self.assertEqual(result, '2026-08-26 09:55:00')

    def test_custom_format(self):
        hms = str_to_hms('2026-08-26 09:55:00')
        result = hms_to_display(hms, fmt='%Y-%m-%d')
        self.assertEqual(result, '2026-08-26')

    def test_zero_returns_empty(self):
        self.assertEqual(hms_to_display(0), '')

    def test_string_zero_returns_empty(self):
        self.assertEqual(hms_to_display('0'), '')

    def test_none_returns_empty(self):
        self.assertEqual(hms_to_display(None), '')

    def test_negative_returns_empty(self):
        self.assertEqual(hms_to_display(-1), '')

    def test_string_negative_returns_empty(self):
        self.assertEqual(hms_to_display('-1'), '')

    def test_explicit_utc_timezone(self):
        hms = str_to_hms('2026-08-26 09:55:00')
        local_display = hms_to_display(hms)
        self.assertIn('2026', local_display)


class TestHmsToDatetime(unittest.TestCase):
    def test_returns_utc_aware(self):
        hms = str_to_hms('2026-08-26 09:55:00')
        dt = hms_to_datetime(hms)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, UTC)

    def test_none_returns_none(self):
        self.assertIsNone(hms_to_datetime(None))

    def test_zero_returns_none(self):
        self.assertIsNone(hms_to_datetime(0))


class TestDatetimeToHms(unittest.TestCase):
    def test_aware_datetime(self):
        dt = datetime(2026, 8, 26, 1, 55, 0, tzinfo=UTC)
        hms = datetime_to_hms(dt)
        self.assertIsInstance(hms, int)
        restored = hms_to_datetime(hms)
        self.assertEqual(restored.year, 2026)
        self.assertEqual(restored.month, 8)
        self.assertEqual(restored.day, 26)
        self.assertEqual(restored.hour, 1)
        self.assertEqual(restored.minute, 55)

    def test_naive_datetime_treated_as_utc(self):
        dt = datetime(2026, 8, 26, 1, 55, 0)
        hms = datetime_to_hms(dt)
        restored = hms_to_datetime(hms)
        self.assertEqual(restored.hour, 1)

    def test_none_returns_none(self):
        self.assertIsNone(datetime_to_hms(None))


class TestDateBoundaries(unittest.TestCase):
    """跨日/跨月/跨年/闰年边界。"""

    def test_cross_day(self):
        hms_23 = str_to_hms('2026-08-26 23:59:59')
        hms_00 = str_to_hms('2026-08-27 00:00:00')
        self.assertLess(hms_23, hms_00)
        diff_hms = hms_00 - hms_23
        self.assertEqual(diff_hms, 10)

    def test_cross_month(self):
        hms_end = str_to_hms('2026-08-31 23:59:59')
        hms_start = str_to_hms('2026-09-01 00:00:00')
        self.assertLess(hms_end, hms_start)

    def test_cross_year(self):
        hms_end = str_to_hms('2026-12-31 23:59:59')
        hms_start = str_to_hms('2027-01-01 00:00:00')
        self.assertLess(hms_end, hms_start)

    def test_leap_year_feb29(self):
        hms = str_to_hms('2028-02-29 12:00:00')
        self.assertIsNotNone(hms)
        display = hms_to_display(hms)
        self.assertIn('2028-02-29', display)

    def test_non_leap_year_feb29_returns_none(self):
        hms = str_to_hms('2027-02-29 12:00:00')
        self.assertIsNone(hms)


class TestTodayRange(unittest.TestCase):
    def test_local_today_before_tomorrow(self):
        today = local_today_start_hms()
        tomorrow = local_tomorrow_start_hms()
        self.assertLess(today, tomorrow)
        diff_seconds = (tomorrow - today) / 10
        self.assertAlmostEqual(diff_seconds, 86400, delta=2)

    def test_utc_today_before_tomorrow(self):
        today = utc_today_start_hms()
        tomorrow = utc_tomorrow_start_hms()
        self.assertLess(today, tomorrow)
        diff_seconds = (tomorrow - today) / 10
        self.assertAlmostEqual(diff_seconds, 86400, delta=2)

    def test_now_within_today_range(self):
        now = utc_now_hms()
        today = utc_today_start_hms()
        tomorrow = utc_tomorrow_start_hms()
        self.assertGreaterEqual(now, today)
        self.assertLess(now, tomorrow)


class TestDateStrToHmsRange(unittest.TestCase):
    def test_valid_date(self):
        start, end = date_str_to_hms_range('2026-08-26')
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertLess(start, end)
        diff_seconds = (end - start) / 10
        self.assertAlmostEqual(diff_seconds, 86400, delta=2)

    def test_roundtrip_start(self):
        start, _ = date_str_to_hms_range('2026-08-26')
        display = hms_to_display(start)
        self.assertTrue(display.startswith('2026-08-26 00:00:00'))

    def test_none_returns_none_pair(self):
        start, end = date_str_to_hms_range(None)
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_empty_returns_none_pair(self):
        start, end = date_str_to_hms_range('')
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_invalid_returns_none_pair(self):
        start, end = date_str_to_hms_range('bad')
        self.assertIsNone(start)
        self.assertIsNone(end)


class TestHmsToDateStr(unittest.TestCase):
    def test_basic(self):
        hms = str_to_hms('2026-08-26 09:55:00')
        self.assertEqual(hms_to_date_str(hms), '2026-08-26')

    def test_none(self):
        self.assertEqual(hms_to_date_str(None), '')


class TestDeprecatedCompat(unittest.TestCase):
    """旧函数仍可调用（Phase T5 前的过渡期）。"""

    def test_get_now_time_format(self):
        result = get_now_time()
        self.assertEqual(len(result), 19)
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')

    def test_get_today_format(self):
        result = get_today()
        self.assertEqual(len(result), 10)
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2}')


class TestMigrationCleanupPreservesNumericText(unittest.TestCase):
    """验证 ensure_business_tables 的 cleanup SQL 不会清零有效时间戳。

    根因复盘：SQLite VARCHAR 列存储的纯数字文本（如 '17877473677'）
    typeof() = 'text'，旧清理条件 `typeof(col) = 'text'` 会误清零。
    修复后条件：仅清零 CAST(col AS INTEGER) = 0 的纯文本（无法解析的文本）。
    """

    def test_numeric_text_not_zeroed_by_cleanup_condition(self):
        """模拟 SQLite 中 VARCHAR 列存有效时间戳文本的场景。"""
        import sqlite3
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE t (create_time VARCHAR(25))')
        conn.execute("INSERT INTO t VALUES ('17877473677')")
        conn.execute("INSERT INTO t VALUES ('17877400000')")
        conn.execute("INSERT INTO t VALUES ('')")
        conn.execute("INSERT INTO t VALUES ('abc')")
        conn.execute("INSERT INTO t VALUES ('2026-08-26 12:00:00')")
        conn.execute("INSERT INTO t VALUES ('0')")
        conn.commit()

        cleanup_sql = (
            "UPDATE t SET create_time = 0 WHERE create_time = '' "
            "OR (create_time IS NOT NULL AND typeof(create_time) = 'text' "
            "AND CAST(create_time AS INTEGER) = 0 AND create_time != '0')"
        )
        conn.execute(cleanup_sql)
        conn.commit()

        rows = conn.execute(
            "SELECT create_time FROM t ORDER BY rowid"
        ).fetchall()
        conn.close()

        self.assertEqual(rows[0][0], '17877473677')
        self.assertEqual(rows[1][0], '17877400000')
        self.assertEqual(rows[2][0], '0')
        self.assertEqual(rows[3][0], '0')
        self.assertEqual(rows[4][0], '2026-08-26 12:00:00')
        self.assertEqual(rows[5][0], '0')

    def test_needs_migration_ignores_numeric_text(self):
        """_column_needs_migration 不应因纯数字文本而返回 True。"""
        import sqlite3
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE t (create_time VARCHAR(25))')
        conn.execute("INSERT INTO t VALUES ('17877473677')")
        conn.commit()

        row = conn.execute(
            "SELECT create_time FROM t WHERE create_time IS NOT NULL "
            "AND create_time != '' AND create_time != '0' "
            "AND typeof(create_time) = 'text' "
            "AND create_time LIKE '____-__-__%' LIMIT 1"
        ).fetchone()
        conn.close()

        self.assertIsNone(row)

    def test_needs_migration_detects_date_text(self):
        """_column_needs_migration 应对日期格式文本返回 True。"""
        import sqlite3
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE t (create_time VARCHAR(25))')
        conn.execute("INSERT INTO t VALUES ('2026-08-26 12:00:00')")
        conn.commit()

        row = conn.execute(
            "SELECT create_time FROM t WHERE create_time IS NOT NULL "
            "AND create_time != '' AND create_time != '0' "
            "AND typeof(create_time) = 'text' "
            "AND create_time LIKE '____-__-__%' LIMIT 1"
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)


if __name__ == '__main__':
    unittest.main()
