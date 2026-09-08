# -*- coding:utf-8 -*-
"""50-bit 时间戳 ID 生成器（OPT-P0-21）。

结构：[38-bit 秒时间戳][12-bit 序列号]
- Epoch: 2024-09-01 00:00:00 UTC (Unix 1725148800)
- 38-bit 秒时间戳: 覆盖 ~8700 年
- 12-bit 序列号: 同秒最多 4096 个 ID
- 总 50 bit, 最大值 1125899906842623 (< JS MAX_SAFE_INTEGER 9007199254740991)
"""
import threading
import time

_EPOCH = 1725148800  # 2024-09-01 00:00:00 UTC
_SEQ_BITS = 12
_SEQ_MASK = (1 << _SEQ_BITS) - 1  # 4095
_JS_MAX_SAFE = 9007199254740991

_lock = threading.Lock()
_last_ts = 0
_seq = 0


def next_id():
    """生成下一个全局唯一、单调递增的 50-bit ID。

    线程安全。同秒内序列号递增，序列号溢出时等待下一秒。

    Returns:
        int: 50-bit 整数（12 位十进制），保证 < JS MAX_SAFE_INTEGER
    """
    global _last_ts, _seq
    with _lock:
        ts = int(time.time()) - _EPOCH
        if ts < 0:
            raise RuntimeError("System clock before ID epoch (2024-09-01)")
        if ts == _last_ts:
            _seq = (_seq + 1) & _SEQ_MASK
            if _seq == 0:
                while int(time.time()) - _EPOCH <= _last_ts:
                    time.sleep(0.01)
                ts = int(time.time()) - _EPOCH
        else:
            _seq = 0
        _last_ts = ts
        new_id = (ts << _SEQ_BITS) | _seq
        if new_id > _JS_MAX_SAFE:
            raise OverflowError(
                "Generated ID %d exceeds JS MAX_SAFE_INTEGER" % new_id)
        return new_id
