#!/usr/bin/python3 
# -*- coding:utf-8 -*-
from flask import request, current_app
from sqlalchemy import select

from app import scheduler, db
from app.decorated import api_deal_return, api_err_return
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.model.job_log_items import JobLogItems
from app.services.cron_service import upsert_cron_by_task_name
from . import api
from ..crons import cron_do

@api.route('/test',methods=['GET','POST'])
@api_deal_return
def test():
    print(request.values.to_dict())
    return 'test'

'''
添加（更新）定时
access_token
task_name 任务名称唯一
task_keyword 备注
run_date 执行时间
day
day_of_week
hour
minute
second
req_url
'''
@api.route('/cron/add',methods=['GET','POST'])
@api.route('/cron',methods=['GET','POST'])
@api_deal_return
def crons():
    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    is_dev = int(CRON_CONFIG.get('is_dev'))
    api_access_token = CRON_CONFIG.get('api_access_token')
    datas = request.values.to_dict()
    task_name = datas.get('task_name')
    access_token = datas.get('access_token')

    if api_access_token:
        if not access_token:
            return api_err_return(msg='access_token不能为空')
        if api_access_token != access_token:
            return api_err_return(msg='access_token错误')

    if not task_name:
        return api_err_return(msg='任务名称不能为空')

    err, _cif = upsert_cron_by_task_name(datas, is_dev, CRON_CONFIG)
    if err:
        return api_err_return(msg=err)

    return 'ok'


'''
更新状态
task_name 任务名称
access_token 
status
'''
@api.route('/cron/status',methods=['GET','POST'])
@api_deal_return
def cron_status():
    datas = request.values.to_dict()

    CRON_CONFIG = current_app.config.get('CRON_CONFIG')

    api_access_token = CRON_CONFIG.get('api_access_token')

    task_name = datas.get('task_name')

    access_token = datas.get('access_token')

    status = datas.get('status')

    if status:
        try:
            if int(status) not in [0,1]:
                return api_err_return(msg='status只能0或者1')
        except:
            return api_err_return(msg='status只能0或者1')

    if api_access_token:

        if not access_token:
            return api_err_return(msg='access_token不能为空')

        if api_access_token != access_token:
            return api_err_return(msg='access_token错误')

    if not task_name:
        return api_err_return(msg='任务名称不能为空')

    ci = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == task_name)
    ).first()
    if not ci:
        return api_err_return(msg='任务不存在')

    if ci.status == -1:
        return api_err_return(msg='任务已下线，不能再操作；请使用新的任务名称新建')

    from app.services.operation_log_service import record_operation

    old_status = ci.status
    if not status:
        #0停止1运行中
        if ci.status == 0:
            #开启
            ci.status = 1
            scheduler.resume_job('cron_%s' % ci.id)
        else:
            ci.status = 0
            #关闭
            scheduler.pause_job('cron_%s' % ci.id)
    else:
        if int(status) == 0 and ci.status != 0:
            ci.status = 0
            # 关闭
            scheduler.pause_job('cron_%s' % ci.id)

        if int(status) == 1 and ci.status !=1:
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

    return 'ok'


@api.route('/cron/retire', methods=['GET', 'POST'])
@api_deal_return
def cron_retire_api():
    from app.services.cron_service import retire_cron_by_task_name

    datas = request.values.to_dict()
    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    api_access_token = CRON_CONFIG.get('api_access_token')
    task_name = datas.get('task_name')
    access_token = datas.get('access_token')

    if api_access_token:
        if not access_token:
            return api_err_return(msg='access_token不能为空')
        if api_access_token != access_token:
            return api_err_return(msg='access_token错误')

    if not task_name:
        return api_err_return(msg='任务名称不能为空')

    err, _ = retire_cron_by_task_name(task_name, datas.get('reason'))
    if err:
        return api_err_return(msg=err)
    return 'ok'


'''
上传执行记录
cronpilot_log_id
content
'''
@api.route('/cron/add_log',methods=['GET','POST'])
@api_deal_return
def cron_add_log():
    datas = request.values.to_dict()

    CRON_CONFIG = current_app.config.get('CRON_CONFIG')

    api_access_token = CRON_CONFIG.get('api_access_token')

    access_token = datas.get('access_token')

    cronpilot_log_id = datas.get('cronpilot_log_id')

    if api_access_token:

        if not access_token:
            return api_err_return(msg='access_token不能为空')

        if api_access_token != access_token:
            return api_err_return(msg='access_token错误')

    if not cronpilot_log_id:
        return api_err_return(msg='cronpilot_log_id 必传哦！')

    content = datas.get('content')
    if not content:
        return api_err_return(msg='日志内容不能为空')

    jl = db.session.scalars(
        select(JobLog).where(JobLog.log_id == cronpilot_log_id)
    ).first()
    if not jl:
        return api_err_return(msg='cronpilot_log_id 不存在')

    jli = JobLogItems(log_id=cronpilot_log_id,content=content)

    db.session.add(jli)

    db.session.commit()

    return 'ok'




