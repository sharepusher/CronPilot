# -*- coding:utf-8 -*-
"""Cron 任务表单校验（Web / API 共用）。"""
from datas.utils.times import get_now_time

from .url_security import validate_callback_url

_WEEK_NAMES = frozenset(['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'])


def _validate_day_of_week(value):
    if not value:
        return True, '', value
    if value.isdigit():
        n = int(value)
        if n not in range(0, 7):
            return False, '【星期】 不在范围内，请检查！', value
        return True, '', value

    value = value.replace('，', ',')
    if ',' in value and '-' in value:
        return False, '【星期】格式有误，同时出现，-', value

    if '-' in value:
        ok, msg, value = _validate_part(value, '星期', (0, 6))
        return ok, msg, value

    if ',' in value:
        for item in value.split(','):
            if not item.isdigit():
                if item not in _WEEK_NAMES:
                    return False, '【星期】 不在范围内，请检查！', value
            elif int(item) not in range(0, 7):
                return False, '【星期】格式有误，数值不在范围内', value
        return True, '', value

    if '*' in value:
        if value.strip() == '*':
            return True, '', value
        if '*/' not in value:
            return False, '【星期】格式有误', value
        if not value.split('/')[-1].isdigit():
            return False, '【星期】格式有误', value
        return True, '', value

    if value not in _WEEK_NAMES:
        return False, '【星期】 不在范围内，请检查！', value
    return True, '', value


def _validate_part(value, label, value_range, out_of_range_msg=None):
    """
    校验日/星期/时/分/秒等 cron 字段。
    value_range: (min, max) 闭区间
    返回 (ok, msg, normalized_value)
    """
    if not value:
        return True, '', value

    lo, hi = value_range
    range_msg = out_of_range_msg or '%s 不在范围内，请检查！' % label

    if value.isdigit():
        n = int(value)
        if n < lo or n > hi:
            return False, range_msg, value
        return True, '', value

    value = value.replace('，', ',')
    if ',' in value and '-' in value:
        return False, '【%s】格式有误，同时出现，-' % label.strip('【】'), value

    if '-' in value:
        parts = value.split('-')
        if len(parts) != 2:
            return False, '【%s】格式有误哦' % label.strip('【】'), value
        p1, p2 = parts[0], parts[-1]
        if not p1.isdigit() or not p2.isdigit():
            return False, '【%s】必须是整数' % label.strip('【】'), value
        if int(p1) >= int(p2):
            return False, '【%s】前面不能大于后面' % label.strip('【】'), value
        if int(p1) < lo or int(p1) > hi or int(p2) < lo or int(p2) > hi:
            return False, '【%s】不在范围内' % label.strip('【】'), value
        return True, '', value

    if ',' in value:
        for item in value.split(','):
            if not item.isdigit():
                return False, '【%s】必须是整数' % label.strip('【】'), value
            if int(item) < lo or int(item) > hi:
                return False, '【%s】格式有误，数值不在范围内' % label.strip('【】'), value
        return True, '', value

    if '*' in value:
        if value.strip() == '*':
            return True, '', value
        if '*/' not in value:
            return False, '【%s】格式有误' % label.strip('【】'), value
        if not value.split('/')[-1].isdigit():
            return False, '【%s】格式有误' % label.strip('【】'), value
        return True, '', value

    return False, '【%s】必须是整数' % label.strip('【】'), value


def validate_cron_form(datas, is_dev, cron_config, *, mode='add', cron_id=None, api_mode=False):
    """
    校验并规范化任务表单。
    成功返回 (None, normalized_dict)；失败返回 (error_message, None)。
    """
    task_name = (datas.get('task_name') or '').strip()
    if not task_name:
        return '任务名称不能为空', None

    task_keyword = (datas.get('task_keyword') or '').strip()
    if not task_keyword:
        return '任务说明不能为空', None
    if len(task_keyword) > 500:
        return '任务说明不能超过500字', None

    run_date = datas.get('run_date') or ''
    ds_ms = (datas.get('ds_ms') or '').strip()

    if mode == 'edit' and ds_ms == '2':
        run_date = ''

    if run_date and run_date < get_now_time('%Y-%m-%d %H:%M'):
        return '设置的时间已过期，请重新设置', None

    day = datas.get('day') or ''
    if day:
        if day.isdigit() and int(day) not in range(1, 32):
            return '日（号）不在范围内，请检查！', None
        ok, msg, day = _validate_part(day, '日', (1, 31))
        if not ok:
            return msg, None

    day_of_week = datas.get('day_of_week') or ''
    if day_of_week:
        ok, msg, day_of_week = _validate_day_of_week(day_of_week)
        if not ok:
            return msg, None

    hour = datas.get('hour') or ''
    if hour:
        ok, msg, hour = _validate_part(hour, '小时', (0, 23))
        if not ok:
            return msg, None

    minute = datas.get('minute') or ''
    if minute:
        ok, msg, minute = _validate_part(minute, '分', (0, 59))
        if not ok:
            return msg, None

    second = datas.get('second') or ''
    if second:
        ok, msg, second = _validate_part(second, '秒', (0, 59))
        if not ok:
            return msg, None

    incomplete_msg = '信息请完整填写！' if api_mode else '请完整填写！'
    if mode == 'add':
        if ds_ms == '1':
            if not run_date:
                return '时间没设置呢！', None
        elif not run_date:
            if not day_of_week and not day and not hour and not minute and not second:
                return incomplete_msg, None
    else:
        if ds_ms == '1':
            if not run_date:
                return '时间没设置呢！', None
        elif not run_date:
            if not day_of_week and not day and not hour and not minute and not second:
                return incomplete_msg, None

    req_url = (datas.get('req_url') or '').strip()
    url_ok, url_msg = validate_callback_url(req_url, cron_config)
    if not url_ok:
        return url_msg, None

    if int(is_dev) == 1:
        second = ''

    return None, {
        'task_name': task_name,
        'task_keyword': task_keyword,
        'run_date': run_date,
        'day': day,
        'day_of_week': day_of_week,
        'hour': hour,
        'minute': minute,
        'second': second,
        'req_url': req_url,
    }


def validate_retire_reason(reason):
    """人工下线原因：trim 后 1～500 字。成功返回 (None, reason)。"""
    reason = (reason or '').strip()
    if not reason:
        return '请填写下线原因', None
    if len(reason) > 500:
        return '下线原因不能超过500字', None
    return None, reason
