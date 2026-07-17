# -*- coding:utf-8 -*-
"""Cron 任务表单校验（Web / API 共用）。"""
from datas.utils.times import get_now_time

from .url_security import validate_callback_url
from .cron_schedule_display import schedule_configured_from_normalized

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
    成功返回 (None, normalized_dict, None)；失败返回 (error_message, None, field_key)。
    field_key 供前端定位表单项（如 task_name、hour、cron_div）。
    """
    def _fail(msg, field=None):
        return msg, None, field

    task_name = (datas.get('task_name') or '').strip()
    if not task_name:
        return _fail('请填写任务名称', 'task_name')

    task_keyword = (datas.get('task_keyword') or '').strip()
    if not task_keyword:
        return _fail('请填写任务说明（用途、需求链接或特殊情况）', 'task_keyword')
    if len(task_keyword) > 500:
        return _fail('任务说明不能超过 500 字', 'task_keyword')

    run_date = datas.get('run_date') or ''
    ds_ms = (datas.get('ds_ms') or '').strip()
    if not api_mode:
        if ds_ms and ds_ms not in ('1', '2'):
            return _fail('请选择定时方式：「定时模式」或「具体时间」', 'ds_ms')
        if not ds_ms:
            # Web 表单通常必传；缺省时按是否有具体时间推断，兼容旧调用
            ds_ms = '1' if str(run_date).strip() else '2'

    if mode == 'edit' and ds_ms == '2':
        run_date = ''

    if run_date and run_date < get_now_time('%Y-%m-%d %H:%M'):
        return _fail('具体时间已过期，请重新选择未来的执行时刻', 'run_date')

    day = datas.get('day') or ''
    if day:
        if day.isdigit() and int(day) not in range(1, 32):
            return _fail('「日(号)」须在 1～31 之间', 'day')
        ok, msg, day = _validate_part(day, '日', (1, 31))
        if not ok:
            return _fail(msg, 'day')

    day_of_week = datas.get('day_of_week') or ''
    if day_of_week:
        ok, msg, day_of_week = _validate_day_of_week(day_of_week)
        if not ok:
            return _fail(msg, 'day_of_week')

    hour = datas.get('hour') or ''
    if hour:
        ok, msg, hour = _validate_part(hour, '小时', (0, 23))
        if not ok:
            return _fail(msg, 'hour')

    minute = datas.get('minute') or ''
    if minute:
        ok, msg, minute = _validate_part(minute, '分', (0, 59))
        if not ok:
            return _fail(msg, 'minute')

    second = datas.get('second') or ''
    if second:
        ok, msg, second = _validate_part(second, '秒', (0, 59))
        if not ok:
            return _fail(msg, 'second')

    schedule_incomplete_msg = (
        '定时模式需至少填写「小时」「分钟」「星期」或「日(号)」中的一项；'
        '或改选「具体时间」并填写执行时刻'
    )
    if api_mode:
        schedule_incomplete_msg = 'API：' + schedule_incomplete_msg

    if mode == 'add':
        if ds_ms == '1':
            if not run_date:
                return _fail('已选择「具体时间」，请填写下方的执行时刻', 'run_date')
        elif not run_date:
            if not day_of_week and not day and not hour and not minute and not second:
                return _fail(schedule_incomplete_msg, 'cron_div')
    else:
        if ds_ms == '1':
            if not run_date:
                return _fail('已选择「具体时间」，请填写下方的执行时刻', 'run_date')
        elif not run_date:
            if not day_of_week and not day and not hour and not minute and not second:
                return _fail(schedule_incomplete_msg, 'cron_div')

    req_url = (datas.get('req_url') or '').strip()
    if not req_url:
        return _fail('请填写触发 URL（到点由调度器发起 GET/POST 请求）', 'req_url')
    url_ok, url_msg = validate_callback_url(req_url, cron_config)
    if not url_ok:
        return _fail(url_msg, 'req_url')

    req_method = (datas.get('req_method') or 'GET').upper().strip()
    if req_method not in ('GET', 'POST'):
        return _fail('请求方式只能为 GET 或 POST', 'req_method')

    req_body = (datas.get('req_body') or '').strip()
    if req_body:
        import json
        try:
            parsed = json.loads(req_body)
        except ValueError:
            return _fail('请求 body 格式有误，须为合法的 JSON 字符串', 'req_body')
        if not isinstance(parsed, dict):
            return _fail('请求 body 须为 JSON 对象（object）', 'req_body')

    req_method = (datas.get('req_method') or 'GET').upper().strip()
    if req_method not in ('GET', 'POST'):
        return '回调请求方式只能为 GET 或 POST', None

    req_body = (datas.get('req_body') or '').strip()
    if req_body:
        import json
        try:
            parsed = json.loads(req_body)
        except ValueError:
            return '请求 body 格式有误，须为合法的 JSON 字符串', None
        if not isinstance(parsed, dict):
            return '请求 body 须为 JSON 对象（object）', None

    if int(is_dev) == 1:
        second = ''

    normalized = {
        'task_name': task_name,
        'task_keyword': task_keyword,
        'run_date': run_date,
        'day': day,
        'day_of_week': day_of_week,
        'hour': hour,
        'minute': minute,
        'second': second,
        'req_url': req_url,
        'req_method': req_method,
        'req_body': req_body,
    }
    if not schedule_configured_from_normalized(normalized, ds_ms):
        return _fail(schedule_incomplete_msg, 'cron_div')

    return None, normalized, None


def validate_retire_reason(reason):
    """人工下线原因：trim 后 1～500 字。成功返回 (None, reason)。"""
    reason = (reason or '').strip()
    if not reason:
        return '请填写下线原因', None
    if len(reason) > 500:
        return '下线原因不能超过500字', None
    return None, reason
