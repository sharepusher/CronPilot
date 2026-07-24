#!/usr/bin/python3 
# -*- coding:utf-8 -*-
from flask import request, current_app
from sqlalchemy import select

from app import scheduler, db
from app.decorated import api_deal_return, api_err_return
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.model.job_log_items import JobLogItems
from datas.utils.json import api_return
from app.services.cron_service import upsert_cron_by_task_name
from . import api
from .schemas import CronUpsertIn, CronStatusIn, CronRetireIn, AddLogIn
from ..crons import cron_do


# ---------------------------------------------------------------------------
# Batch 4.1 — /api/test（无输入，验证迁移机制）
# ---------------------------------------------------------------------------

@api.get('/test')
@api.doc(summary='接口连通性测试', tags=['系统'])
def test():
    return api_return(errcode=0, errmsg='test')


# ---------------------------------------------------------------------------
# Batch 4.2 — /api/cron/add_log（业务方回传执行进度）
# ---------------------------------------------------------------------------

@api.post('/cron/add_log')
@api.doc(
    summary='业务方回传执行进度',
    description=(
        '业务方在处理 CronPilot 回调时，可调用此接口写入阶段性进度记录。\n\n'
        '**认证**：conf.ini 配置 `api_access_token` 后，需通过 '
        '`Authorization: Bearer <token>` Header 或 `access_token` query/form 参数传递。'
    ),
    tags=['执行日志'],
)
@api.input(AddLogIn, location='form', arg_name='form_data')
def cron_add_log(form_data):
    cronpilot_log_id = form_data.get('cronpilot_log_id')
    content = form_data.get('content')

    jl = db.session.scalars(
        select(JobLog).where(JobLog.log_id == cronpilot_log_id)
    ).first()
    if not jl:
        return api_return(errcode=1, errmsg='cronpilot_log_id 不存在')

    jli = JobLogItems(log_id=cronpilot_log_id, content=content)
    db.session.add(jli)
    db.session.commit()

    return api_return(errcode=0, errmsg='ok')


# ---------------------------------------------------------------------------
# Batch 4.3 — /api/cron/retire（下线任务）
# ---------------------------------------------------------------------------

@api.post('/cron/retire')
@api.doc(
    summary='永久下线定时任务',
    description=(
        '将任务置为下线（status=-1）状态，不可恢复，后续须以新 task_name 新建。\n\n'
        '**认证**：同 /api/cron/add_log。'
    ),
    tags=['任务管理'],
)
@api.input(CronRetireIn, location='form', arg_name='form_data')
def cron_retire_api(form_data):
    from app.services.cron_service import retire_cron_by_task_name

    task_name = form_data.get('task_name')
    reason = form_data.get('reason')

    err, _ = retire_cron_by_task_name(task_name, reason)
    if err:
        return api_return(errcode=1, errmsg=err)
    return api_return(errcode=0, errmsg='ok')


# ---------------------------------------------------------------------------
# Batch 4.4 — /api/cron/status（切换任务状态）
# ---------------------------------------------------------------------------

@api.post('/cron/status')
@api.doc(
    summary='切换或指定任务运行状态',
    description=(
        '不传 status 时取反（运行中→停止，停止→运行中）。\n\n'
        'status=0 停止，status=1 运行中。\n\n'
        '**认证**：同 /api/cron/add_log。'
    ),
    tags=['任务管理'],
)
@api.input(CronStatusIn, location='form', arg_name='form_data')
def cron_status(form_data):
    task_name = form_data.get('task_name')
    status = form_data.get('status')

    CRON_CONFIG = current_app.config.get('CRON_CONFIG')

    ci = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == task_name)
    ).first()
    if not ci:
        return api_return(errcode=1, errmsg='任务不存在')

    if ci.status == -1:
        return api_return(errcode=1, errmsg='任务已下线，不能再操作；请使用新的任务名称新建')

    from app.services.operation_log_service import record_operation

    old_status = ci.status
    if status is None:
        if ci.status == 0:
            ci.status = 1
            scheduler.resume_job('cron_%s' % ci.id)
        else:
            ci.status = 0
            scheduler.pause_job('cron_%s' % ci.id)
    else:
        if status == 0 and ci.status != 0:
            ci.status = 0
            scheduler.pause_job('cron_%s' % ci.id)
        if status == 1 and ci.status != 1:
            ci.status = 1
            scheduler.resume_job('cron_%s' % ci.id)

    db.session.add(ci)
    db.session.commit()
    if old_status != ci.status:
        record_operation(
            action='toggle_status',
            target_id=ci.id,
            task_name=ci.task_name or '',
            detail={'status': {'old': old_status, 'new': ci.status}},
        )

    return api_return(errcode=0, errmsg='ok')


# ---------------------------------------------------------------------------
# Batch 4.5 — /api/cron（新增/更新任务，最复杂）
# ---------------------------------------------------------------------------

@api.post('/cron')
@api.doc(
    summary='新增或更新定时任务',
    description=(
        '以 task_name 为唯一键，存在则更新，不存在则新建。\n\n'
        '**调度字段**：至少填写 hour/minute/day/day_of_week 之一（定时模式），或填写 run_date（具体时间模式）。\n\n'
        '**认证**：同 /api/cron/add_log。'
    ),
    tags=['任务管理'],
)
@api.input(CronUpsertIn, location='form', arg_name='form_data')
def crons(form_data):
    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    is_dev = int(CRON_CONFIG.get('is_dev'))

    err, _cif = upsert_cron_by_task_name(form_data, is_dev, CRON_CONFIG)
    if err:
        return api_return(errcode=1, errmsg=err)

    return api_return(errcode=0, errmsg='ok')


# ===========================================================================
# 向后兼容别名（旧 URL / GET+POST 两用，保留 @api_deal_return，不入 Swagger）
# ===========================================================================

@api.route('/cron/add', methods=['GET', 'POST'])
@api_deal_return
def crons_legacy():
    """旧路径兼容层：/api/cron/add（GET 或 POST form），不做 Schema 注入。
    新调用方请使用 POST /api/cron。
    access_token 鉴权由 Blueprint before_request 统一处理。
    """
    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    is_dev = int(CRON_CONFIG.get('is_dev'))
    datas = request.values.to_dict()
    task_name = datas.get('task_name')

    if not task_name:
        return api_err_return(msg='任务名称不能为空')

    err, _cif = upsert_cron_by_task_name(datas, is_dev, CRON_CONFIG)
    if err:
        return api_err_return(msg=err)

    return 'ok'
