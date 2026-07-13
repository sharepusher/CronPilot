# -*- coding:utf-8 -*-
"""Cron 任务写入与调度注册（Web / API 共用）。"""
from sqlalchemy import select

from app import db, scheduler
from app.services.cron_validator import validate_cron_form
from app.services.job_log_service import delete_job_logs_for_cron
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog


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
    cif.status = 1


def create_cron(normalized):
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
        status=1,
    )
    db.session.add(cif)
    db.session.commit()
    register_cron_job(cif.id, normalized)
    return cif


def update_cron(cif, normalized):
    apply_normalized_to_model(cif, normalized)
    db.session.add(cif)
    db.session.commit()
    register_cron_job(cif.id, normalized)
    return cif


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

