# -*- coding:utf-8 -*-
import traceback

from sqlalchemy import and_, select

from app import scheduler, db
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.model.job_log_items import JobLogItems
from datas.utils.json import json_response
from . import main
from flask import render_template, request, redirect, session, current_app

from app.rbac.decorators import authorize_resource, require_permission, session_group_ids
from app.rbac.policy import role_bypasses_scope
from app.rbac.scope import (
    build_scope_filter_clause,
    normalize_scope_fields,
    user_can_assign_group,
)
from app.rbac.services import list_resource_groups
from app.services.cron_service import add_cron_web, edit_cron_web

from ..common.functions import wechat_info_err, web_api_return


def _scope_groups_for_form():
    """admin 见全部组；其它用户仅见所属组。"""
    role = session.get('role') or ''
    try:
        all_groups = list_resource_groups()
    except Exception:
        return []
    if role_bypasses_scope(role):
        return all_groups
    allowed = set(session_group_ids())
    return [g for g in all_groups if g.id in allowed]


def _scope_form_context():
    """非 admin：任务强制落在所属业务组，不可选 GLOBAL。"""
    role = session.get('role') or ''
    groups = _scope_groups_for_form()
    locked = not role_bypasses_scope(role)
    return {
        'scope_groups': groups,
        'scope_locked': locked,
        'default_group_id': groups[0].id if locked and len(groups) == 1 else None,
    }


def _apply_scope_from_form(datas):
    """从 POST 字段解析 scope，写入 datas；失败返回错误字符串。"""
    role = session.get('role') or ''
    gids = session_group_ids()
    # 非 admin：强制 GROUP，且 group 必须属于本人
    if not role_bypasses_scope(role):
        if not gids:
            return '当前账号未绑定业务组，无法创建/编辑任务'
        group_id = datas.get('group_id')
        if group_id is None or group_id == '':
            if len(gids) == 1:
                group_id = gids[0]
            else:
                return '请选择所属业务组'
        try:
            group_id = int(group_id)
        except (TypeError, ValueError):
            return '业务组无效'
        if group_id not in set(int(x) for x in gids):
            return '只能将任务放在本人所属业务组内'
        datas['scope_type'] = 'GROUP'
        datas['group_id'] = group_id
        return None

    err, scope_type, group_id = normalize_scope_fields(
        datas.get('scope_type'),
        datas.get('group_id'),
    )
    if err:
        return err
    if not user_can_assign_group(role, gids, group_id):
        return '不能将任务分配到未所属的业务组'
    datas['scope_type'] = scope_type
    datas['group_id'] = group_id
    return None


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
    scope_clause = build_scope_filter_clause(
        session.get('role') or '',
        session_group_ids(),
    )
    if scope_clause is not None:
        filter_arr.append(scope_clause)

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
    cif = db.session.get(CronInfos, id) if id else None
    if id:
        if not cif:
            page_data = (
                db.session.query(JobLog)
                .filter(JobLog.cron_info_id == -1)
                .order_by(db.desc(JobLog.id))
                .paginate(page=page, per_page=20)
            )
            if 'page' in keywords:
                del keywords['page']
            return render_template("job_log_list.html", page_data=page_data, keywords=keywords)
        denied = authorize_resource('log:read', cif)
        if denied:
            return denied

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
    jl = db.session.scalars(
        select(JobLog).where(JobLog.log_id == log_id)
    ).first()
    if not jl:
        return render_template("job_log_item_list.html", page_data=[])
    cif = db.session.get(CronInfos, jl.cron_info_id)
    denied = authorize_resource('log:read', cif)
    if denied:
        return denied
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
    denied = authorize_resource('log:read', cif)
    if denied:
        return denied
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
    scope_clause = build_scope_filter_clause(
        session.get('role') or '',
        session_group_ids(),
    )
    if scope_clause is not None:
        filter_arr.append(scope_clause)

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
    scope_ctx = _scope_form_context()
    if request.method == 'POST':
        try:
            datas = request.values.to_dict()
            scope_err = _apply_scope_from_form(datas)
            if scope_err:
                return web_api_return(code=1, msg=scope_err)
            err = add_cron_web(datas, is_dev, CRON_CONFIG)
            if err:
                return web_api_return(code=1, msg=err)
            return web_api_return(code=0, msg='添加成功', url='/cron_list')
        except Exception as e:
            trace_info = traceback.format_exc()
            wechat_info_err(str(e), trace_info)
            return web_api_return(code=1, msg=str(e), url='/cron_list')

    return render_template(
        "cron_add.html",
        is_dev=is_dev,
        **scope_ctx,
    )


@main.route('/cron_edit', methods=['GET', 'POST'])
@require_permission('cron:write')
def cron_edit():
    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    is_dev = int(CRON_CONFIG.get('is_dev'))
    id = request.values.get('id')
    cif = db.session.get(CronInfos, id)
    if not cif:
        return web_api_return(code=1, msg='任务不存在', url='/cron_list')
    denied = authorize_resource('cron:write', cif)
    if denied:
        return denied
    if cif.status == -1:
        return web_api_return(code=1, msg='任务已下线，不能编辑；请新建任务', url='/cron_list')
    if request.method == 'POST':
        # 编辑不改作用域（表单亦不展示）；创建/更新时间只读且不展示
        datas = request.values.to_dict()
        err = edit_cron_web(datas, is_dev, CRON_CONFIG, id)
        if err:
            return web_api_return(code=1, msg=err)
        return web_api_return(code=0, msg='修改成功！', url='/cron_list')

    return render_template(
        "cron_edit.html",
        cif=cif,
        is_dev=is_dev,
    )


@main.route('/update_status', methods=['GET', 'POST'])
@require_permission('cron:write')
def update_status():
    from app.services.operation_log_service import record_operation

    id = request.args.get('id')
    cif = db.session.get(CronInfos, id)
    if not cif:
        return web_api_return(code=1, msg='项目不存在',url='/cron_list')
    denied = authorize_resource('cron:write', cif)
    if denied:
        return denied
    if cif.status == -1:
        return web_api_return(code=1, msg='任务已下线，不能启动或暂停；请新建任务')
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
    record_operation(
        action='toggle_status',
        target_id=cif.id,
        task_name=cif.task_name or '',
        detail={'status': {'old': status, 'new': _status}},
    )
    msg = '已启动' if _status == 1 else '已暂停'
    return web_api_return(code=0, msg=msg)


@main.route('/cron_retire', methods=['GET', 'POST'])
@require_permission('cron:retire')
def cron_retire():
    from app.services.cron_service import retire_cron_by_id

    id = request.args.get('id') or request.values.get('id')
    cif = db.session.get(CronInfos, id)
    if not cif:
        return web_api_return(code=1, msg='项目不存在', url='/cron_list')
    denied = authorize_resource('cron:retire', cif)
    if denied:
        return denied
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


@main.route('/operation_log_list', methods=['GET', 'POST'])
@require_permission('operation:read')
def operation_log_list():
    from datas.model.operation_log import OperationLog
    from app.services.operation_log_service import (
        format_detail_summary,
        operation_action_label,
        operation_channel_label,
        operation_result_label,
    )

    keywords = request.args.to_dict()
    page = int(request.args.get('page') or 1)
    task_name = (keywords.get('task_name') or '').strip()
    operator_name = (keywords.get('operator_name') or '').strip()
    action = (keywords.get('action') or '').strip()
    channel = (keywords.get('channel') or '').strip()
    beg_time = (keywords.get('beg_time') or '').strip()
    end_time = (keywords.get('end_time') or '').strip()

    filters = []
    if task_name:
        filters.append(OperationLog.task_name.like('%{}%'.format(task_name)))
    if operator_name:
        filters.append(OperationLog.operator_name.like('%{}%'.format(operator_name)))
    if action:
        filters.append(OperationLog.action == action)
    if channel:
        filters.append(OperationLog.channel == channel)
    if beg_time:
        filters.append(OperationLog.create_time >= beg_time)
    if end_time:
        filters.append(OperationLog.create_time <= end_time)

    role = session.get('role') or ''
    if not role_bypasses_scope(role):
        scope_clause = build_scope_filter_clause(role, session_group_ids())
        visible_ids = select(CronInfos.id)
        if scope_clause is not None:
            visible_ids = visible_ids.where(scope_clause)
        filters.append(
            and_(
                OperationLog.target_type == 'cron',
                OperationLog.target_id.in_(visible_ids),
            )
        )

    page_data = (
        db.session.query(OperationLog)
        .filter(*filters)
        .order_by(db.desc(OperationLog.id))
        .paginate(page=page, per_page=20)
    )
    if 'page' in keywords:
        del keywords['page']
    return render_template(
        'operation_log_list.html',
        page_data=page_data,
        keywords=keywords,
        operation_action_label=operation_action_label,
        operation_channel_label=operation_channel_label,
        operation_result_label=operation_result_label,
        format_detail_summary=format_detail_summary,
    )


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
