# -*- coding:utf-8 -*-
import traceback

from sqlalchemy import select

from app import scheduler, db
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.model.job_log_items import JobLogItems
from datas.utils.json import json_response
from . import main
from flask import render_template, request, redirect, session, current_app

from app.rbac.decorators import require_permission
from app.services.cron_service import add_cron_web, edit_cron_web

from ..common.functions import wechat_info_err, web_api_return


@main.route('/cron_list', methods=['GET', 'POST'])
@main.route('/', methods=['GET', 'POST'])
@require_permission('cron:read')
def cron_list():
    keyword = request.args.to_dict()
    page = int(request.args.get('page') or 1)
    task_name = keyword.get('task_name')
    filter_arr = []
    if task_name:
        filter_arr.append(CronInfos.task_name.like('%{}%'.format(task_name)))

    page_data = (
        db.session.query(CronInfos)
        .filter(*filter_arr)
        .order_by(db.desc(CronInfos.status), db.desc(CronInfos.task_name))
        .paginate(page=page, per_page=20)
    )
    if 'page' in keyword: del keyword['page']
    return render_template("cron_list.html", page_data=page_data, keyword=keyword)


@main.route('/api_doc', methods=['GET', 'POST'])
@require_permission('cron:read')
def api_doc():
    return render_template("api_doc.html")


@main.route('/job_log_list', methods=['GET', 'POST'])
@require_permission('log:read')
def job_log_list():
    keywords = request.args.to_dict()

    page = int(request.args.get('page') or 1)
    id = request.args.get('id')

    page_data = (
        db.session.query(JobLog)
        .filter(JobLog.cron_info_id == id)
        .order_by(db.desc(JobLog.id))
        .paginate(page=page, per_page=20)
    )
    if 'page' in keywords:
        del keywords['page']

    return render_template("job_log_list.html", page_data=page_data, keywords=keywords)

@main.route('/job_log_item_list', methods=['GET', 'POST'])
@require_permission('log:read')
def job_log_item_list():
    log_id = request.args.get('log_id')
    page_data = db.session.scalars(
        select(JobLogItems).where(JobLogItems.log_id == log_id)
    ).all()

    return render_template("job_log_item_list.html", page_data=page_data)


@main.route('/job_log_detail', methods=['GET'])
@require_permission('log:read')
def job_log_detail():
    job_log_id = request.args.get('id')
    jl = db.session.get(JobLog, job_log_id)
    if not jl:
        return render_template("job_log_detail.html", jl=None, cif=None, items=[])
    cif = db.session.get(CronInfos, jl.cron_info_id)
    items = []
    if jl.log_id:
        items = db.session.scalars(
            select(JobLogItems).where(JobLogItems.log_id == jl.log_id)
        ).all()
    return render_template("job_log_detail.html", jl=jl, cif=cif, items=items)


@main.route('/job_log_all_list', methods=['GET', 'POST'])
@require_permission('log:read')
def job_log_all_list():
    keywords = request.args.to_dict()

    page = int(request.args.get('page') or 1)

    filter_arr = []
    task_name = keywords.get('task_name')
    if task_name:
        filter_arr.append(CronInfos.task_name.like('%{}%'.format(task_name)))
    beg_time = keywords.get('beg_time')
    end_time = keywords.get('end_time')
    if beg_time and end_time:
        filter_arr.append(JobLog.create_time.between(beg_time,end_time))

    page_data = (
        db.session.query(JobLog, CronInfos)
        .join(CronInfos, CronInfos.id == JobLog.cron_info_id)
        .filter(*filter_arr)
        .order_by(db.desc(JobLog.id))
        .paginate(page=page, per_page=20)
    )

    if 'page' in keywords:
        del keywords['page']

    return render_template("job_log_all_list.html", page_data=page_data, keywords=keywords)


@main.route('/job_log_delete', methods=['GET', 'POST'])
@require_permission('log:read')
def job_log_delete():
    return json_response(errcode=1, errmsg='已禁止删除执行记录', status=410)


@main.route('/job_batch_delete', methods=['GET', 'POST'])
@require_permission('log:read')
def job_batch_delete():
    return json_response(errcode=1, errmsg='已禁止删除执行记录', status=410)


@main.route('/cron_add', methods=['GET', 'POST'])
@require_permission('cron:write')
def cron_add():
    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    is_dev = int(CRON_CONFIG.get('is_dev'))
    if request.method == 'POST':
        try:
            err = add_cron_web(request.values.to_dict(), is_dev, CRON_CONFIG)
            if err:
                return web_api_return(code=1, msg=err)
            return web_api_return(code=0, msg='添加成功', url='/cron_list')
        except Exception as e:
            trace_info = traceback.format_exc()
            wechat_info_err(str(e), trace_info)
            return web_api_return(code=1, msg=str(e), url='/cron_list')

    return render_template("cron_add.html", is_dev=is_dev)


@main.route('/cron_edit', methods=['GET', 'POST'])
@require_permission('cron:write')
def cron_edit():
    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    is_dev = int(CRON_CONFIG.get('is_dev'))
    id = request.values.get('id')
    cif = db.session.get(CronInfos, id)
    if cif and cif.status == -1:
        return web_api_return(code=1, msg='任务已下线，不能编辑；请新建任务', url='/cron_list')
    if request.method == 'POST':
        err = edit_cron_web(request.values.to_dict(), is_dev, CRON_CONFIG, id)
        if err:
            return web_api_return(code=1, msg=err)
        return web_api_return(code=0, msg='修改成功！', url='/cron_list')

    return render_template("cron_edit.html", cif=cif, is_dev=is_dev)


@main.route('/update_status', methods=['GET', 'POST'])
@require_permission('cron:write')
def update_status():
    id = request.args.get('id')
    cif = db.session.get(CronInfos, id)
    if not cif:
        return web_api_return(code=1, msg='项目不存在',url='/cron_list')
    if cif.status == -1:
        return web_api_return(code=1, msg='任务已下线，不能启停；请新建任务')
    status = cif.status
    _status = 0
    if status == 0:
        _status = 1
        scheduler.resume_job('cron_%s' % cif.id)
    else:
        scheduler.pause_job('cron_%s' % cif.id)
    cif.status = _status
    db.session.add(cif)
    db.session.commit()
    return web_api_return(code=0, msg='操作成功')


@main.route('/cron_retire', methods=['GET', 'POST'])
@require_permission('cron:retire')
def cron_retire():
    from app.services.cron_service import retire_cron_by_id

    id = request.args.get('id') or request.values.get('id')
    cif = db.session.get(CronInfos, id)
    if not cif:
        return web_api_return(code=1, msg='项目不存在', url='/cron_list')
    if cif.status == -1:
        if request.method == 'GET' and not request.values.get('reason'):
            return render_template('cron_retire.html', cif=cif, already=True)
        return web_api_return(code=0, msg='任务已下线', url='/cron_list')
    if request.method == 'GET':
        return render_template('cron_retire.html', cif=cif, already=False)
    err, _ = retire_cron_by_id(id, request.values.get('reason'))
    if err:
        return web_api_return(code=1, msg=err)
    return web_api_return(code=0, msg='任务已下线', url='/cron_list')


@main.route('/cron_del', methods=['GET', 'POST'])
@require_permission('cron:read')
def cron_del():
    return json_response(errcode=1, errmsg='已禁止删除任务，请使用下线', status=410)


@main.route('/cron_batch_del', methods=['GET', 'POST'])
@require_permission('cron:read')
def cron_batch_del():
    return json_response(errcode=1, errmsg='已禁止删除任务，请使用下线', status=410)


@main.route('/check_pass', methods=['GET', 'POST'])
def check_pass():
    next_url = request.args.get('next', '')
    target = f'/rbac/login?next={next_url}' if next_url else '/rbac/login'
    if request.method == 'GET':
        return redirect(target)
    return redirect(target, code=307)

@main.route('/logout')
def logout():
    session.clear()
    return redirect("/check_pass")
