# -*- coding: utf-8 -*-
"""日志格式契约测试：验证 JSON 字段与 timestamp ISO-8601 合规性。

回归防护：
- timestamp 必须可被 datetime.fromisoformat() 解析（防止 %f 字面量泄漏）
- 必备字段（level、logger、trace_id 等）必须存在
"""
import datetime
import io
import logging
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TestJsonTimestamp(unittest.TestCase):
    """_CronPilotJsonFormatter.formatTime 必须产出合法 ISO-8601 时间串。"""

    def _make_formatter(self):
        from app.logging_config import _CronPilotJsonFormatter
        fmt_str = (
            '%(asctime)s %(levelname)s %(name)s %(filename)s '
            '%(lineno)d %(thread)d %(message)s'
        )
        return _CronPilotJsonFormatter(fmt_str, datefmt='%Y-%m-%dT%H:%M:%S.%f%z')

    def test_timestamp_no_literal_percent_f(self):
        """timestamp 字段不得包含字面量 '%f'。"""
        import json
        formatter = self._make_formatter()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(formatter)

        logger = logging.getLogger('test_ts_pct_f')
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.info('probe message')

        record_str = stream.getvalue().strip()
        self.assertTrue(record_str, 'No log output produced')
        data = json.loads(record_str)
        ts = data.get('timestamp', '')
        self.assertNotIn('%f', ts, 'timestamp contains literal %%f: %r' % ts)

    def test_timestamp_parseable_as_iso8601(self):
        """timestamp 字段必须可被 datetime.fromisoformat() 解析。"""
        import json
        formatter = self._make_formatter()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(formatter)

        logger = logging.getLogger('test_ts_iso')
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.info('probe iso')

        data = json.loads(stream.getvalue().strip())
        ts = data.get('timestamp', '')
        try:
            parsed = datetime.datetime.fromisoformat(ts)
        except (ValueError, TypeError) as exc:
            self.fail('timestamp %r is not valid ISO-8601: %s' % (ts, exc))
        self.assertIsNotNone(parsed)

    def test_required_fields_present(self):
        """JSON 日志记录必须含 level、logger、message、timestamp。"""
        import json
        formatter = self._make_formatter()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(formatter)

        logger = logging.getLogger('test_fields')
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.info('fields probe')

        data = json.loads(stream.getvalue().strip())
        for field in ('level', 'logger', 'message', 'timestamp'):
            self.assertIn(field, data, 'Required field %r missing from JSON log' % field)


if __name__ == '__main__':
    unittest.main()
