#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""时间工具模块 — BIGINT (UTC, 百毫秒) + 旧格式兼容。

存储约定（OPT-PERF-TIMESTAMP-BIGINT）：
  - 所有时间字段存为 BIGINT，值 = UTC epoch × 10（百毫秒精度）
  - 写入使用 utc_now_hms()
  - 展示使用 hms_to_display()（自动按 display_timezone 或服务器本地时区还原）
  - API 响应使用 hms_to_str()（返回 ISO 8601 字符串，对外无感知）

旧格式函数（get_now_time / get_today / get_next_time）标记为 DEPRECATED，
Phase T5 完成后移除。
"""
import datetime
import time

_UTC = datetime.timezone.utc

# ─── 全局展示时区（方案 C：conf.ini display_timezone）───

_display_tz_cache = None
_display_tz_loaded = False


def _get_display_tz():
    """读取 conf.ini 的 display_timezone，返回 datetime.timezone 或 None（本地）。
    结果缓存在模块级变量中，避免每次读取文件。
    """
    global _display_tz_cache, _display_tz_loaded
    if _display_tz_loaded:
        return _display_tz_cache
    _display_tz_loaded = True
    try:
        from configs import configs
        tz_name = configs('display_timezone')
    except Exception:
        tz_name = ''
    if not tz_name or not tz_name.strip():
        _display_tz_cache = None
        return None
    tz_name = tz_name.strip()
    try:
        try:
            from zoneinfo import ZoneInfo
            _display_tz_cache = ZoneInfo(tz_name)
        except ImportError:
            import pytz
            _display_tz_cache = pytz.timezone(tz_name)
    except Exception:
        _display_tz_cache = None
    return _display_tz_cache


def reset_display_tz_cache():
    """测试/热重载时清除时区缓存。"""
    global _display_tz_cache, _display_tz_loaded
    _display_tz_cache = None
    _display_tz_loaded = False


# ─── 写入（返回 BIGINT）───

def utc_now_hms():
    """当前 UTC 时间，百毫秒精度 BIGINT。"""
    return int(time.time() * 10)


def utc_today_start_hms():
    """今日 UTC 00:00:00 对应的百毫秒 BIGINT。"""
    now = datetime.datetime.now(_UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp() * 10)


def utc_tomorrow_start_hms():
    """明日 UTC 00:00:00 对应的百毫秒 BIGINT。"""
    now = datetime.datetime.now(_UTC)
    tomorrow = (now + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(tomorrow.timestamp() * 10)


def local_today_start_hms():
    """今日本地 00:00:00 对应的百毫秒 BIGINT（UTC epoch）。
    用于替换 get_today() + LIKE 模式。
    """
    now = datetime.datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp() * 10)


def local_tomorrow_start_hms():
    """明日本地 00:00:00 对应的百毫秒 BIGINT（UTC epoch）。"""
    now = datetime.datetime.now()
    tomorrow = (now + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(tomorrow.timestamp() * 10)


def datetime_to_hms(dt):
    """datetime → 百毫秒 BIGINT。
    如果 dt 无时区信息，按 UTC 处理。
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    return int(dt.timestamp() * 10)


# ─── 展示（BIGINT → 可读字符串）───

def hms_to_display(hms_value, fmt='%Y-%m-%d %H:%M:%S', tz=None):
    """百毫秒 BIGINT → 可读字符串。
    tz=None 时使用 display_timezone 配置或服务器本地时区。
    """
    if not hms_value:
        return ''
    try:
        iv = int(hms_value)
    except (ValueError, TypeError):
        return ''
    if iv <= 0:
        return ''
    try:
        ts = iv / 10.0
        if tz is None:
            tz = _get_display_tz()
        dt = datetime.datetime.fromtimestamp(ts, tz=tz)
        return dt.strftime(fmt)
    except (ValueError, TypeError, OSError, OverflowError):
        return ''


def hms_to_datetime(hms_value):
    """百毫秒 BIGINT → datetime (UTC aware)。"""
    if not hms_value:
        return None
    try:
        iv = int(hms_value)
    except (ValueError, TypeError):
        return None
    if iv <= 0:
        return None
    try:
        return datetime.datetime.fromtimestamp(iv / 10.0, tz=_UTC)
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def hms_to_str(hms_value, fmt='%Y-%m-%d %H:%M:%S'):
    """百毫秒 BIGINT → 'YYYY-MM-DD HH:MM:SS' 字符串。
    用于 API 响应序列化（保持对外格式不变）。
    展示时区与 hms_to_display 相同。
    """
    return hms_to_display(hms_value, fmt=fmt)


def hms_to_date_str(hms_value):
    """百毫秒 BIGINT → 'YYYY-MM-DD' 字符串。"""
    return hms_to_display(hms_value, fmt='%Y-%m-%d')


# ─── 兼容互转（旧格式 ↔ BIGINT）───

def str_to_hms(time_str):
    """'YYYY-MM-DD HH:MM:SS'（本地时间）→ 百毫秒 BIGINT (UTC)。
    用于数据迁移、旧测试数据适配、前端传入的时间范围参数。
    """
    if not time_str or str(time_str).strip() == '':
        return None
    try:
        dt = datetime.datetime.strptime(str(time_str)[:19], '%Y-%m-%d %H:%M:%S')
        return int(dt.timestamp() * 10)
    except (ValueError, TypeError):
        return None


def date_str_to_hms_range(date_str):
    """'YYYY-MM-DD' → (start_hms, end_hms) 本地时间范围的 UTC BIGINT。
    start = 当日 00:00:00, end = 次日 00:00:00（不含）。
    """
    if not date_str:
        return None, None
    try:
        d = datetime.datetime.strptime(str(date_str)[:10], '%Y-%m-%d')
        start = int(d.timestamp() * 10)
        end = int((d + datetime.timedelta(days=1)).timestamp() * 10)
        return start, end
    except (ValueError, TypeError):
        return None, None


# ─── DEPRECATED（Phase T5 完成后移除）───

def get_now_time(format='%Y-%m-%d %H:%M:%S'):
    """[DEPRECATED] 返回服务器本地时间字符串。新代码使用 utc_now_hms()。"""
    return time.strftime(format, time.localtime(time.time()))


def get_next_time(format='%Y-%m-%d %H:%M:%S', **ke):
    """[DEPRECATED] 返回若干秒/分/天后的本地时间字符串。"""
    tiimes = (datetime.datetime.now() + datetime.timedelta(**ke)).strftime(format)
    return tiimes


def get_today(format='%Y-%m-%d'):
    """[DEPRECATED] 返回今日本地日期字符串。新代码使用 local_today_start_hms()。"""
    return time.strftime(format, time.localtime(time.time()))
