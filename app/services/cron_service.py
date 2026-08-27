# -*- coding:utf-8 -*-
"""Cron 任务写入与调度注册（Web / API 共用）。"""
import logging

from sqlalchemy import select

from app import db, scheduler
from app.services.cron_validator import validate_cron_form, validate_retire_reason
from datas.model.cron_infos import CronInfos
from datas.utils.times import utc_now_hms

# 系统自动下线固定文案（LIFECYCLE-2）
_log = logging.getLogger(__name__)

RETIRE_REASON_ONE_SHOT = '一次性任务执行完成（系统）'
RETIRE_REASON_EXECUTOR = '调度执行器异常移除（系统）'
RETIRE_REASON_ORPHAN = 'JobStore 无对应任务，系统对账下线'


def stamp_last_operator(cif, operator=None):
    """写入最近发布/编辑/下线操作人（列表「发布人」列）。"""
    from app.services.operation_log_service import resolve_operator_from_request

    op = operator if operator is not None else resolve_operator_from_request()
    cif.last_operator_name = (getattr(op, 'operator_name', None) or '')[:120]
    cif.last_operated_at = utc_now_hms()


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
    from app.services.cron_schedule_display import schedule_configured_from_normalized

    run_date = normalized.get('run_date') or ''
    ds_ms = '1' if run_date else '2'
    if not schedule_configured_from_normalized(normalized, ds_ms):
        raise ValueError('未配置调度策略，无法注册任务')
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
    cif.timeout_sec = normalized.get('timeout_sec')
    cif.updated_at = utc_now_hms()
    if 'scope_type' in normalized:
        cif.scope_type = normalized['scope_type'] or 'GLOBAL'


def create_cron(normalized):
    from app.services.operation_log_service import record_operation, snapshot_cron

    now = utc_now_hms()
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
        timeout_sec=normalized.get('timeout_sec'),
        status=1,
        created_at=now,
        updated_at=now,
        scope_type=normalized.get('scope_type') or 'GLOBAL',
    )
    stamp_last_operator(cif)
    db.session.add(cif)
    db.session.flush()  # 获取 cif.id，用于写入 task_groups
    # OPT-P1-11：任务归属单个业务组（GROUP 时恰好一条 task_groups 记录）
    group_id = normalized.get('group_id')
    if group_id:
        from datas.model.task_group import TaskGroup
        db.session.add(TaskGroup(task_id=cif.id, group_id=int(group_id)))
    # OPT-P1-11：标签 — 同步 task_tags（标签隔离：传递 group_id）
    tag_names = normalized.get('tag_names')
    if tag_names is not None:
        from app.services.tag_service import sync_task_tags
        from flask import session as flask_session
        sync_task_tags(cif.id, tag_names,
                       created_by=flask_session.get('username') or '',
                       group_id=group_id)
    db.session.commit()
    register_cron_job(cif.id, normalized)
    record_operation(
        action='create_cron',
        target_id=cif.id,
        task_name=cif.task_name or '',
        detail=snapshot_cron(cif),
    )
    return cif


def update_cron(cif, normalized, resume_after_save=False):
    from app.services.operation_log_service import (
        build_cron_diff,
        record_operation,
        snapshot_cron,
    )

    before = snapshot_cron(cif)
    was_paused = cif.status == 0
    apply_normalized_to_model(cif, normalized)
    if resume_after_save and was_paused:
        cif.status = 1
    stamp_last_operator(cif)
    db.session.add(cif)
    # OPT-P1-11：同步 task_groups 关联（单组）
    new_group_id = normalized.get('group_id')
    if new_group_id is not None:
        from datas.model.task_group import TaskGroup
        db.session.execute(
            TaskGroup.__table__.delete().where(TaskGroup.task_id == cif.id)
        )
        if new_group_id:
            db.session.add(TaskGroup(task_id=cif.id, group_id=int(new_group_id)))
    # OPT-P1-11：同步标签（标签隔离：传递 group_id）
    tag_names = normalized.get('tag_names')
    if tag_names is not None:
        from app.services.tag_service import sync_task_tags
        from flask import session as flask_session
        task_gid = new_group_id if new_group_id is not None else normalized.get('group_id')
        sync_task_tags(cif.id, tag_names,
                       created_by=flask_session.get('username') or '',
                       group_id=task_gid if task_gid else None)
    db.session.commit()
    register_cron_job(cif.id, normalized)
    if cif.status == 0:
        try:
            scheduler.pause_job('cron_%s' % cif.id)
        except Exception:
            _log.warning('pause_job failed for cron_%s', cif.id, exc_info=True)
    record_operation(
        action='update_cron',
        target_id=cif.id,
        task_name=cif.task_name or '',
        detail=build_cron_diff(before, snapshot_cron(cif)),
    )
    return cif


def apply_retire(cif, reason, operator=None):
    """将任务标为下线并写原因/时间；调用方负责 remove_job 与 commit。"""
    cif.status = -1
    cif.retire_reason = reason
    cif.retired_at = utc_now_hms()
    stamp_last_operator(cif, operator=operator)
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
        _log.warning('remove_job failed for cron_%s during retire', cif.id, exc_info=True)
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
        _log.warning('remove_job failed for cron_%s during retire', cif.id, exc_info=True)
    db.session.commit()
    _record_retire(cif)
    return None, cif


def upsert_cron_by_task_name(datas, is_dev, cron_config):
    """
    API /cron 添加或更新：按 task_name 查找。
    返回 (error_msg, cif)；error_msg 为 None 表示成功。
    """
    err, normalized, _field = validate_cron_form(
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
    err, normalized, field = validate_cron_form(datas, is_dev, cron_config, mode='add')
    if err:
        return err, field
    if 'scope_type' in datas:
        normalized['scope_type'] = datas.get('scope_type') or 'GLOBAL'
        normalized['group_id'] = datas.get('group_id') or None
    # OPT-P1-11：标签
    if 'tag_names' in datas:
        normalized['tag_names'] = datas['tag_names']
    exists = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == normalized['task_name'])
    ).first()
    if exists:
        return '任务名称「%s」已被占用，请更换名称' % normalized['task_name'], 'task_name'
    create_cron(normalized)
    return None, None


def edit_cron_web(datas, is_dev, cron_config, cron_id):
    err, normalized, field = validate_cron_form(
        datas, is_dev, cron_config, mode='edit', cron_id=cron_id
    )
    if err:
        return err, field
    if 'scope_type' in datas:
        normalized['scope_type'] = datas.get('scope_type') or 'GLOBAL'
        normalized['group_id'] = datas.get('group_id') or None
    # OPT-P1-11：标签
    if 'tag_names' in datas:
        normalized['tag_names'] = datas['tag_names']
    dup = db.session.scalars(
        select(CronInfos).where(
            CronInfos.task_name == normalized['task_name'],
            CronInfos.id != cron_id,
        )
    ).first()
    if dup:
        return '任务名称「%s」已被占用，请更换名称' % normalized['task_name'], 'task_name'
    cif = db.session.get(CronInfos, cron_id)
    if not cif:
        return '任务不存在', None
    if cif.status == -1:
        return '任务已下线，不能编辑；请新建任务', None
    resume = (datas.get('resume_after_save') or '').strip() in ('1', 'on', 'true', 'True')
    update_cron(cif, normalized, resume_after_save=resume)
    return None, None

