# -*- coding:utf-8 -*-
import traceback

from sqlalchemy import delete, select

from app import scheduler, db
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.model.job_log_items import JobLogItems
from datas.utils.times import get_now_time
from . import main
from flask import render_template, request, redirect, session, current_app, jsonify, url_for

from app.auth.password import verify_login_password
from app.rbac.decorators import require_permission
from app.services.cron_service import add_cron_web, edit_cron_web
from app.services.job_log_service import delete_job_logs_for_cron

from ..common.functions import wechat_info_err, web_api_return
from ..decorated import login_required


@main.route('/cron_list', methods=['GET', 'POST'])
@main.route('/', methods=['GET', 'POST'])
@login_required
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
@login_required
def api_doc():
    return render_template("api_doc.html")


@main.route('/job_log_list', methods=['GET', 'POST'])
@login_required
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
@login_required
def job_log_item_list():
    log_id = request.args.get('log_id')
    page_data = db.session.scalars(
        select(JobLogItems).where(JobLogItems.log_id == log_id)
    ).all()

    return render_template("job_log_item_list.html", page_data=page_data)


@main.route('/job_log_detail', methods=['GET'])
@login_required
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
@login_required
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
@login_required
def job_log_delete():
    datas = request.values.to_dict()
    job_log_id = datas.get('job_log_id')
    job_logs = db.session.get(JobLog, job_log_id)
    if not job_logs:
        return web_api_return(code=1,msg='信息不存在')
    db.session.delete(job_logs)
    db.session.commit()

    return web_api_return(code=0,msg='删除成功')

@main.route('/job_batch_delete', methods=['GET', 'POST'])
@login_required
def job_batch_delete():
    ids = request.form.getlist('id')
    db.session.execute(delete(JobLog).where(JobLog.id.in_(ids)))
    db.session.commit()
    return web_api_return(code=0, msg='操作成功', url='/job_log_all_list')

@main.route('/cron_add', methods=['GET', 'POST'])
@login_required
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
@login_required
def cron_edit():
    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    is_dev = int(CRON_CONFIG.get('is_dev'))
    id = request.values.get('id')
    cif = db.session.get(CronInfos, id)
    if request.method == 'POST':
        err = edit_cron_web(request.values.to_dict(), is_dev, CRON_CONFIG, id)
        if err:
            return web_api_return(code=1, msg=err)
        return web_api_return(code=0, msg='修改成功！', url='/cron_list')

    return render_template("cron_edit.html", cif=cif, is_dev=is_dev)


@main.route('/update_status', methods=['GET', 'POST'])
@login_required
def update_status():
    id = request.args.get('id')
    cif = db.session.get(CronInfos, id)
    if not cif:
        return web_api_return(code=1, msg='项目不存在',url='/cron_list')
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

@main.route('/cron_del', methods=['GET', 'POST'])
@require_permission('cron:delete')
def cron_del():
    id = request.args.get('id')
    cif = db.session.get(CronInfos, id)
    if not cif:
        return web_api_return(code=1, msg='项目不存在', url='/cron_list')
    cron_id = cif.id

    db.session.delete(cif)

    try:
        scheduler.remove_job('cron_%s' % cron_id)
    except:
        pass

    delete_job_logs_for_cron(cron_id)

    db.session.commit()
    return web_api_return(code=0, msg='操作成功', url='/cron_list')

@main.route('/cron_batch_del', methods=['GET', 'POST'])
@login_required
def cron_batch_del():
    ids = request.form.getlist('id')
    db.session.execute(delete(CronInfos).where(CronInfos.id.in_(ids)))
    db.session.execute(delete(JobLog).where(JobLog.cron_info_id.in_(ids)))
    db.session.commit()

    try:
        for cron_id in ids:
            scheduler.remove_job('cron_%s' % cron_id)
    except:
        pass

    return web_api_return(code=0, msg='操作成功', url='/cron_list')

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