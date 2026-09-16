# -*- coding:utf-8 -*-
"""将 cron_infos 调度字段译为人类可读文案（列表第 3 列上行）。

下次触发时间 / 有效 crontab 与 APScheduler CronTrigger 默认值对齐
（空 minute + 有 hour → minute=0，而非 Unix crontab 的 *）。
"""
import re
from datetime import datetime


def _part(value):
    return (value or '').strip()


def _normalized_from_item(item):
    return {
        'run_date': _part(getattr(item, 'run_date', None)),
        'day_of_week': _part(getattr(item, 'day_of_week', None)),
        'day': _part(getattr(item, 'day', None)),
        'hour': _part(getattr(item, 'hour', None)),
        'minute': _part(getattr(item, 'minute', None)),
        'second': _part(getattr(item, 'second', None)),
    }


def scheduler_cron_kwargs_from_item(item):
    """与 register_cron_job / reschedule 使用同一 build_scheduler_kwargs。"""
    from app.services.cron_service import build_scheduler_kwargs
    return build_scheduler_kwargs(_normalized_from_item(item))


def cron_trigger_from_item(item):
    """构造与调度注册语义一致的 CronTrigger；一次性 / 非 cron / 未配置返回 None。"""
    if _part(getattr(item, 'run_date', None)):
        return None
    if not _schedule_configured(item):
        return None
    kw = scheduler_cron_kwargs_from_item(item)
    if kw.get('trigger') != 'cron':
        return None
    trigger_kwargs = {k: v for k, v in kw.items() if k != 'trigger'}
    if not trigger_kwargs:
        return None
    from apscheduler.triggers.cron import CronTrigger
    return CronTrigger(**trigger_kwargs)


def _to_naive_local(dt):
    """将 Trigger 返回的 aware datetime 转为本地 naive，供相对时间运算。"""
    if dt is None:
        return None
    if getattr(dt, 'tzinfo', None) is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


def next_fire_datetime(item, now=None):
    """返回与 APScheduler 一致的下一次触发时间（本地 naive）。

    run_date 一次性任务返回 None（由调用方单独处理）。
    """
    trigger = cron_trigger_from_item(item)
    if trigger is None:
        return None
    if now is None:
        now = datetime.now()
    try:
        nxt = trigger.get_next_fire_time(None, now)
    except (TypeError, ValueError):
        return None
    return _to_naive_local(nxt)


def cron_fire_interval_seconds(item, now=None):
    """用 Trigger 连续两次 next 估算调度间隔（秒）；失败返回 None。"""
    trigger = cron_trigger_from_item(item)
    if trigger is None:
        return None
    if now is None:
        now = datetime.now()
    try:
        n1 = trigger.get_next_fire_time(None, now)
        if n1 is None:
            return None
        n2 = trigger.get_next_fire_time(n1, n1)
        if n2 is None:
            return None
        return (n2 - n1).total_seconds()
    except (TypeError, ValueError):
        return None


def effective_crontab_5(item):
    """展示用五段：分 时 日 月 星期（含 APScheduler 默认填充后的值）。

    例：hour=*/2 且 minute 空 → '0 */2 * * *'
    """
    trigger = cron_trigger_from_item(item)
    if trigger is None:
        return ''
    by_name = {f.name: str(f) for f in trigger.fields}
    return '%s %s %s %s %s' % (
        by_name.get('minute', '*'),
        by_name.get('hour', '*'),
        by_name.get('day', '*'),
        by_name.get('month', '*'),
        by_name.get('day_of_week', '*'),
    )


def _is_star(value):
    return not value or value == '*'


def _every_n(value, unit_name):
    """匹配 */n → 每 n 单位；无法识别返回 None。"""
    m = re.match(r'^\*/(\d+)$', value or '')
    if not m:
        return None
    n = int(m.group(1))
    if n <= 0:
        return None
    if n == 1:
        return '每%s' % unit_name
    return '每 %d %s' % (n, unit_name)


def _weekday_label(value):
    mapping = {
        '0': '周日', '7': '周日',
        '1': '周一', '2': '周二', '3': '周三',
        '4': '周四', '5': '周五', '6': '周六',
        'sun': '周日', 'mon': '周一', 'tue': '周二', 'wed': '周三',
        'thu': '周四', 'fri': '周五', 'sat': '周六',
    }
    parts = [p.strip().lower() for p in (value or '').split(',') if p.strip()]
    if not parts:
        return ''
    labels = [mapping.get(p, p) for p in parts]
    return '、'.join(labels)


def _schedule_configured(item):
    """是否填写了可读的周期调度（非 run_date 一次性）。"""
    if _part(getattr(item, 'run_date', None)):
        return True
    for field in ('day_of_week', 'day', 'hour', 'minute', 'second'):
        v = _part(getattr(item, field, None))
        if v and v != '*':
            return True
    return False


def format_cron_expression(item):
    """标准五/六段 cron 格式：分 时 日 月 星期 [秒]（与 APScheduler 有效字段对齐）。"""
    if _part(getattr(item, 'run_date', None)):
        return ''
    if not _schedule_configured(item):
        return ''
    expr = effective_crontab_5(item)
    if not expr:
        return ''
    second = _part(getattr(item, 'second', None))
    # If second is non-trivial (explicitly set), prepend as 6-field
    if second and second != '0' and second != '*':
        expr = '%s %s' % (second, expr)
    return expr


def humanize_schedule(item):
    """
    返回人类可读调度说明。
    例：每 5 分钟 / 每周二 02:00 / 每天 08:30 / 一次性 2026-07-16 10:00
    """
    run_date = _part(getattr(item, 'run_date', None))
    if run_date:
        return '一次性 %s' % run_date

    if not _schedule_configured(item):
        return '未配置调度'

    dow = _part(getattr(item, 'day_of_week', None))
    day = _part(getattr(item, 'day', None))
    hour = _part(getattr(item, 'hour', None))
    minute = _part(getattr(item, 'minute', None))
    second = _part(getattr(item, 'second', None))

    # 秒级高频：*/n 秒且其它为 *
    if second and not _is_star(second):
        every = _every_n(second, '秒')
        if every and _is_star(minute) and _is_star(hour) and _is_star(day) and _is_star(dow):
            return every

    # 分钟级：*/n 分
    if minute and not _is_star(minute):
        every = _every_n(minute, '分钟')
        if every and _is_star(hour) and _is_star(day) and _is_star(dow):
            if second and second not in ('', '*', '0'):
                return '%s（第 %s 秒）' % (every, second)
            return every
        # 固定分钟 + 每小时
        if minute.isdigit() and _is_star(hour) and _is_star(day) and _is_star(dow):
            return '每小时第 %s 分钟' % minute

    # 小时级：*/n 小时
    if hour and not _is_star(hour):
        every = _every_n(hour, '小时')
        if every and _is_star(day) and _is_star(dow):
            m = minute if minute and not _is_star(minute) else '0'
            return '%s 的第 %s 分' % (every, m)

    # 每周某几天的固定时刻
    if dow and not _is_star(dow) and _is_star(day):
        wd = _weekday_label(dow)
        h = hour if hour and not _is_star(hour) else '00'
        m = minute if minute and not _is_star(minute) else '00'
        if h.isdigit():
            h = h.zfill(2)
        if m.isdigit():
            m = m.zfill(2)
        return '每%s %s:%s' % (wd, h, m)

    # 每月某日
    if day and not _is_star(day) and _is_star(dow):
        h = hour if hour and not _is_star(hour) else '00'
        m = minute if minute and not _is_star(minute) else '00'
        if h.isdigit():
            h = h.zfill(2)
        if m.isdigit():
            m = m.zfill(2)
        if day.isdigit():
            return '每月 %s 日 %s:%s' % (day, h, m)
        return '每月 %s 日 %s:%s' % (day, h, m)

    # 每天固定时刻
    if (hour and not _is_star(hour)) or (minute and not _is_star(minute)):
        h = hour if hour and not _is_star(hour) else '00'
        m = minute if minute and not _is_star(minute) else '00'
        if h.isdigit():
            h = h.zfill(2)
        if m.isdigit():
            m = m.zfill(2)
        if _is_star(day) and _is_star(dow):
            return '每天 %s:%s' % (h, m)

    expr = format_cron_expression(item)
    return expr or '按周期触发'


def schedule_configured_from_normalized(normalized, ds_ms):
    """表单规范化后是否具备可执行调度（与列表 humanize 判定一致）。"""
    if (ds_ms or '').strip() == '1':
        return bool(_part(normalized.get('run_date')))
    item = type('_CronItem', (), {})()
    item.run_date = ''
    item.day_of_week = normalized.get('day_of_week') or ''
    item.day = normalized.get('day') or ''
    item.hour = normalized.get('hour') or ''
    item.minute = normalized.get('minute') or ''
    item.second = normalized.get('second') or ''
    return _schedule_configured(item)


def schedule_empty_hint(item, status=None):
    """无执行记录时，结合任务状态给出简短说明。"""
    if status == -1 or status == 0:
        return ''
    if not _schedule_configured(item) and not _part(getattr(item, 'run_date', None)):
        return '调度未配置，不会自动执行'
    return '等待首次触发'


def format_duration(raw_value):
    """将耗时（秒，字符串或数值）格式化为可读文案。
    例：0.318 → '318ms'，1.089 → '1.1s'，空/0 → '—'
    """
    if not raw_value:
        return '—'
    try:
        secs = float(raw_value)
    except (TypeError, ValueError):
        return str(raw_value)
    if secs <= 0:
        return '0ms'
    if secs >= 1:
        return '{:.1f}s'.format(secs)
    return '{}ms'.format(int(secs * 1000))
