# -*- coding:utf-8 -*-
"""Cron 任务写入与调度注册（Web / API 共用）。"""
from sqlalchemy import select

from app import db, scheduler
from app.services.cron_validator import validate_cron_form, validate_retire_reason
from datas.model.cron_infos import CronInfos
from datas.utils.times import get_now_time

# 系统自动下线固定文案（LIFECYCLE-2）
RETIRE_REASON_ONE_SHOT = '一次性任务执行完成（系统）'
RETIRE_REASON_EXECUTOR = '调度执行器异常移除（系统）'
RETIRE_REASON_ORPHAN = 'JobStore 无对应任务，系统对账下线'


def build_scheduler_kwargs(normalized):
    cron_datas = {}
    run_date = normalized.get('run_date') or ''
    if run_date:
        cron_datas['trigger'] = 'date'
        cron_datas['run_date'] = run_date
    else:
        cron_datas['trigger'] = 'cron'
        if normalized.get('day_of_week'):
            cron_datas['day_of_week'] = normalized['day_of_week']
        if normalized.get('hour'):
            cron_datas['hour'] = normalized['hour']
        if normalized.get('minute'):
            cron_datas['minute'] = normalized['minute']
        if normalized.get('day'):
            cron_datas['day'] = normalized['day']
        second = normalized.get('second') or ''
        if second and second != '*':
            cron_datas['second'] = second
    return cron_datas


def register_cron_job(cron_id, normalized):
    from app.crons import cron_do

    cron_datas = build_scheduler_kwargs(normalized)
    scheduler.add_job(
        'cron_%s' % cron_id,
        func=cron_do,
        args=[cron_id],
        replace_existing=True,
        **cron_datas,
    )


def apply_normalized_to_model(cif, normalized):
    cif.task_name = normalized['task_name']
    cif.task_keyword = normalized['task_keyword']
    cif.run_date = normalized['run_date']
    cif.day_of_week = normalized['day_of_week']
    cif.day = normalized['day']
    cif.hour = normalized['hour']
    cif.minute = normalized['minute']
    cif.second = normalized['second']
    cif.req_url = normalized['req_url']
    cif.req_method = normalized.get('req_method', 'GET')
    cif.req_body = normalized.get('req_body', '')
    cif.status = 1
    cif.updated_at = get_now_time()
    if 'scope_type' in normalized:
        cif.scope_type = normalized['scope_type'] or 'GLOBAL'
    if 'group_id' in normalized:
        cif.group_id = normalized['group_id']


def create_cron(normalized):
    from app.services.operation_log_service import record_operation, snapshot_cron

    now = get_now_time()
    cif = CronInfos(
        task_name=normalized['task_name'],
        task_keyword=normalized['task_keyword'],
        run_date=normalized['run_date'],
        day_of_week=normalized['day_of_week'],
        day=normalized['day'],
        hour=normalized['hour'],
        minute=normalized['minute'],
        second=normalized['second'],
        req_url=normalized['req_url'],
        req_method=normalized.get('req_method', 'GET'),
        req_body=normalized.get('req_body', ''),
        status=1,
        created_at=now,
        updated_at=now,
        scope_type=normalized.get('scope_type') or 'GLOBAL',
        group_id=normalized.get('group_id'),
    )
    db.session.add(cif)
    db.session.commit()
    register_cron_job(cif.id, normalized)
    record_operation(
        action='create_cron',
        target_id=cif.id,
        task_name=cif.task_name or '',
        detail=snapshot_cron(cif),
    )
    return cif


def update_cron(cif, normalized):
    from app.services.operation_log_service import (
        build_cron_diff,
        record_operation,
        snapshot_cron,
    )

    before = snapshot_cron(cif)
    apply_normalized_to_model(cif, normalized)
    db.session.add(cif)
    db.session.commit()
    register_cron_job(cif.id, normalized)
    record_operation(
        action='update_cron',
        target_id=cif.id,
        task_name=cif.task_name or '',
        detail=build_cron_diff(before, snapshot_cron(cif)),
    )
    return cif


def apply_retire(cif, reason):
    """将任务标为下线并写原因/时间；调用方负责 remove_job 与 commit。"""
    cif.status = -1
    cif.retire_reason = reason
    cif.retired_at = get_now_time()
    db.session.add(cif)


def _record_retire(cif):
    from app.services.operation_log_service import record_operation, snapshot_cron

    record_operation(
        action='retire_cron',
        target_id=cif.id,
        task_name=cif.task_name or '',
        detail={
            'reason': cif.retire_reason or '',
            'retired_at': cif.retired_at or '',
            'snapshot': snapshot_cron(cif),
        },
    )


def retire_cron_by_id(cron_id, reason):
    """
    Web 下线。返回 (error_msg, cif)；error_msg 为 None 表示成功。
    """
    err, reason = validate_retire_reason(reason)
    if err:
        return err, None
    cif = db.session.get(CronInfos, cron_id)
    if not cif:
        return '项目不存在', None
    if cif.status == -1:
        return None, cif
    apply_retire(cif, reason)
    try:
        scheduler.remove_job('cron_%s' % cif.id)
    except Exception:
        pass
    db.session.commit()
    _record_retire(cif)
    return None, cif


def retire_cron_by_task_name(task_name, reason):
    """
    API 下线。返回 (error_msg, cif)；error_msg 为 None 表示成功。
    """
    err, reason = validate_retire_reason(reason)
    if err:
        return err, None
    cif = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == task_name)
    ).first()
    if not cif:
        return '任务不存在', None
    if cif.status == -1:
        return None, cif
    apply_retire(cif, reason)
    try:
        scheduler.remove_job('cron_%s' % cif.id)
    except Exception:
        pass
    db.session.commit()
    _record_retire(cif)
    return None, cif


def upsert_cron_by_task_name(datas, is_dev, cron_config):
    """
    API /cron 添加或更新：按 task_name 查找。
    返回 (error_msg, cif)；error_msg 为 None 表示成功。
    """
    err, normalized = validate_cron_form(
        datas, is_dev, cron_config, mode='add', api_mode=True
    )
    if err:
        return err, None

    task_name = normalized['task_name']
    cif = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == task_name)
    ).first()
    if not cif:
        cif = create_cron(normalized)
    else:
        if cif.status == -1:
            return '任务已下线，不能更新；请使用新的任务名称新建', None
        update_cron(cif, normalized)
    return None, cif


def add_cron_web(datas, is_dev, cron_config):
    err, normalized = validate_cron_form(datas, is_dev, cron_config, mode='add')
    if err:
        return err
    if 'scope_type' in datas:
        normalized['scope_type'] = datas.get('scope_type') or 'GLOBAL'
        normalized['group_id'] = datas.get('group_id')
    exists = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == normalized['task_name'])
    ).first()
    if exists:
        return '任务名称已存在'
    create_cron(normalized)
    return None


def edit_cron_web(datas, is_dev, cron_config, cron_id):
    err, normalized = validate_cron_form(
        datas, is_dev, cron_config, mode='edit', cron_id=cron_id
    )
    if err:
        return err
    if 'scope_type' in datas:
        normalized['scope_type'] = datas.get('scope_type') or 'GLOBAL'
        normalized['group_id'] = datas.get('group_id')
    dup = db.session.scalars(
        select(CronInfos).where(
            CronInfos.task_name == normalized['task_name'],
            CronInfos.id != cron_id,
        )
    ).first()
    if dup:
        return '任务名称已存在已存在'
    cif = db.session.get(CronInfos, cron_id)
    if not cif:
        return '任务不存在'
    if cif.status == -1:
        return '任务已下线，不能编辑；请新建任务'
    update_cron(cif, normalized)
    return None

