# -*- coding:utf-8 -*-
"""tests/test_id_generator.py — 50-bit ID 生成器测试（OPT-P0-21）。"""
import threading
import time
import unittest
from unittest.mock import patch

from datas.utils.id_generator import (
    _EPOCH, _JS_MAX_SAFE, _SEQ_BITS, _SEQ_MASK, next_id,
)
import datas.utils.id_generator as _mod


class TestNextId(unittest.TestCase):
    """next_id() 基础属性测试。"""

    def setUp(self):
        _mod._last_ts = 0
        _mod._seq = 0

    def test_returns_positive_int(self):
        val = next_id()
        self.assertIsInstance(val, int)
        self.assertGreater(val, 0)

    def test_12_digit_decimal(self):
        val = next_id()
        self.assertGreaterEqual(len(str(val)), 10)
        self.assertLessEqual(len(str(val)), 15)

    def test_js_safe(self):
        val = next_id()
        self.assertLessEqual(val, _JS_MAX_SAFE)

    def test_monotonic_increasing(self):
        ids = [next_id() for _ in range(100)]
        for i in range(1, len(ids)):
            self.assertGreater(ids[i], ids[i - 1],
                               "ID %d not > %d at index %d" % (ids[i], ids[i - 1], i))

    def test_unique(self):
        ids = [next_id() for _ in range(1000)]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate IDs found")


class TestThreadSafety(unittest.TestCase):
    """多线程并发生成不重复。"""

    def setUp(self):
        _mod._last_ts = 0
        _mod._seq = 0

    def test_concurrent_unique(self):
        results = []
        errors = []

        def worker():
            try:
                for _ in range(200):
                    results.append(next_id())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, "Errors: %s" % errors)
        self.assertEqual(len(results), 1000)
        self.assertEqual(len(set(results)), 1000, "Duplicate IDs in concurrent test")


class TestSequenceOverflow(unittest.TestCase):
    """同秒序列号溢出时等待下一秒。"""

    def setUp(self):
        _mod._last_ts = 0
        _mod._seq = 0

    def test_overflow_waits_next_second(self):
        base_ts = int(time.time()) - _EPOCH
        _mod._last_ts = base_ts
        _mod._seq = _SEQ_MASK  # 4095 — next call overflows

        val = next_id()
        new_ts = val >> _SEQ_BITS
        self.assertGreater(new_ts, base_ts,
                           "Expected to advance to next second on overflow")


class TestClockBeforeEpoch(unittest.TestCase):
    """系统时钟早于 epoch 时抛出异常。"""

    def setUp(self):
        _mod._last_ts = 0
        _mod._seq = 0

    def test_raises_on_past_clock(self):
        with patch('datas.utils.id_generator.time') as mock_time:
            mock_time.time.return_value = _EPOCH - 100
            mock_time.sleep = time.sleep
            with self.assertRaises(RuntimeError):
                next_id()


class TestIdStructure(unittest.TestCase):
    """验证 ID 结构：高位为秒时间戳，低 12 位为序列号。"""

    def setUp(self):
        _mod._last_ts = 0
        _mod._seq = 0

    def test_decompose(self):
        before = int(time.time()) - _EPOCH
        val = next_id()
        after = int(time.time()) - _EPOCH

        ts_part = val >> _SEQ_BITS
        seq_part = val & _SEQ_MASK

        self.assertGreaterEqual(ts_part, before)
        self.assertLessEqual(ts_part, after)
        self.assertEqual(seq_part, 0)  # first ID in this second

    def test_second_id_has_seq_1(self):
        _ = next_id()
        val2 = next_id()
        seq_part = val2 & _SEQ_MASK
        self.assertEqual(seq_part, 1)


if __name__ == '__main__':
    unittest.main()
