# -*- coding:utf-8 -*-
import traceback

from sqlalchemy import and_

from app import scheduler, db
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.utils.json import json_response
from . import main
from flask import render_template, request, redirect, session, current_app, url_for

from app.rbac.decorators import authorize_resource, require_permission, session_group_ids
from app.rbac.policy import role_bypasses_scope
from app.rbac.scope import (
    SCOPE_GLOBAL,
    SCOPE_GROUP,
    build_scope_filter_clause,
    normalize_scope_fields,
    user_can_assign_group,
)
from app.rbac.services import list_resource_groups
from app.security.csrf import csrf_protect
from app.services.cron_service import add_cron_web, edit_cron_web
from app.services.job_log_filter import job_log_outcome_clause
from app.services.pagination import PageQuery
from app.repositories.cron_repository import CronRepository
from app.repositories.job_log_repository import JobLogRepository
from app.repositories.operation_log_repository import OperationLogRepository


def _parse_log_outcome_param():
    """无 outcome 参数时默认 not_success（排障优先）；outcome=all 表示全部。"""
    if 'outcome' not in request.args:
        return 'not_success'
    raw = (request.args.get('outcome') or '').strip().lower()
    if raw in ('', 'all'):
        return 'all'
    if raw in ('success', 'fail', 'error', 'not_success', 'unknown'):
        return raw
    return 'not_success'

from ..common.functions import wechat_info_err, web_api_return


def _cron_repo():
    return CronRepository(db.session)


def _job_log_repo():
    return JobLogRepository(db.session)


def _operation_log_repo():
    return OperationLogRepository(db.session)


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


def _parse_ui_scope_view(role, group_ids, scope_view, group_id_raw):
    """可视范围内的二次过滤；越权 group_id 回退 all。返回 (scope_view, group_id, clause|None)。"""
    sv = (scope_view or 'all').strip().lower()
    if sv not in ('all', 'global', 'group'):
        sv = 'all'
    gid = None
    if sv == 'group':
        try:
            gid = int(group_id_raw)
        except (TypeError, ValueError):
            return 'all', None, None
        if not role_bypasses_scope(role) and gid not in set(group_ids or []):
            return 'all', None, None
        return sv, gid, and_(
            CronInfos.scope_type == SCOPE_GROUP,
            CronInfos.group_id == gid,
        )
    if sv == 'global':
        return sv, None, CronInfos.scope_type == SCOPE_GLOBAL
    return 'all', None, None


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
    page_query = PageQuery.from_args(request.args)
    task_name = keyword.get('task_name')
    role = session.get('role') or ''
    group_ids = session_group_ids()
    filter_arr = []
    if task_name:
        filter_arr.append(CronInfos.task_name.like('%{}%'.format(task_name)))
    scope_clause = build_scope_filter_clause(role, group_ids)
    if scope_clause is not None:
        filter_arr.append(scope_clause)

    scope_view, scope_group_id, ui_scope_clause = _parse_ui_scope_view(
        role,
        group_ids,
        keyword.get('scope_view'),
        keyword.get('group_id'),
    )
    if ui_scope_clause is not None:
        filter_arr.append(ui_scope_clause)

    life_status = keyword.get('status')
    if life_status in ('0', '1', '-1'):
        filter_arr.append(CronInfos.status == int(life_status))

    health = (keyword.get('health') or '').strip().lower()
    repo = _cron_repo()
    metrics = repo.metrics(
        list(filter_arr),
        cron_config=current_app.config.get('CRON_CONFIG'),
    )
    page_data = repo.paginate_list(page_query, filters=filter_arr, health=health)

    health_by_id = repo.health_by_cron_ids([item.id for item in page_data.items])

    scope_groups = _scope_groups_for_form()
    group_name_by_id = {g.id: g.name for g in scope_groups}
    # admin 侧栏需要全量组名；非 admin 仅所属组
    if role_bypasses_scope(role):
        try:
            group_name_by_id = {g.id: g.name for g in list_resource_groups()}
            scope_groups = list_resource_groups()
        except Exception:
            pass

    if 'page' in keyword:
        del keyword['page']
    keyword['scope_view'] = scope_view
    if scope_group_id is not None:
        keyword['group_id'] = str(scope_group_id)
    elif 'group_id' in keyword and scope_view != 'group':
        keyword.pop('group_id', None)

    failing_tasks = repo.top_failing(filter_arr, limit=5)
    recent_ok_tasks = repo.top_recent_ok(filter_arr, limit=5)

    return render_template(
        "cron_list.html",
        page_data=page_data,
        keyword=keyword,
        metrics=metrics,
        health_by_id=health_by_id,
        scope_groups=scope_groups,
        group_name_by_id=group_name_by_id,
        scope_view=scope_view,
        scope_group_id=scope_group_id,
        scope_nav_mode=(
            'sidebar' if role_bypasses_scope(role) or len(scope_groups) >= 5
            else ('segment' if scope_groups else 'none')
        ),
        is_admin_scope=role_bypasses_scope(role),
        list_role=role,
        failing_tasks=failing_tasks,
        recent_ok_tasks=recent_ok_tasks,
    )


@main.route('/api_doc', methods=['GET', 'POST'])
@require_permission('cron:read')
def api_doc():
    return render_template("api_doc.html")


@main.route('/job_log_list', methods=['GET', 'POST'])
@require_permission('log:read')
def job_log_list():
    keywords = request.args.to_dict()

    page_query = PageQuery.from_args(request.args)
    id = request.args.get('id')
    repo = _job_log_repo()
    cif = db.session.get(CronInfos, id) if id else None
    if id:
        if not cif:
            page_data = repo.paginate_empty(page_query)
            if 'page' in keywords:
                del keywords['page']
            return render_template(
                "job_log_list.html",
                page_data=page_data,
                keywords=keywords,
                outcome='all',
            )
        denied = authorize_resource('log:read', cif)
        if denied:
            return denied

    # 单任务 iframe：缺省全部；仅 URL 显式带 outcome 时筛选
    if 'outcome' not in request.args:
        outcome = 'all'
    else:
        raw = (request.args.get('outcome') or '').strip().lower()
        if raw in ('', 'all'):
            outcome = 'all'
        elif raw in ('success', 'fail', 'error', 'not_success', 'unknown'):
            outcome = raw
        else:
            outcome = 'all'
    page_data = repo.paginate_for_cron(page_query, id, outcome=outcome)
    if 'page' in keywords:
        del keywords['page']
    keywords['outcome'] = outcome
    keywords['id'] = id

    return render_template(
        "job_log_list.html",
        page_data=page_data,
        keywords=keywords,
        outcome=outcome,
    )

@main.route('/job_log_item_list', methods=['GET', 'POST'])
@require_permission('log:read')
def job_log_item_list():
    log_id = request.args.get('log_id')
    repo = _job_log_repo()
    jl = repo.get_by_log_id(log_id)
    if not jl:
        return render_template("job_log_item_list.html", page_data=[])
    cif = db.session.get(CronInfos, jl.cron_info_id)
    denied = authorize_resource('log:read', cif)
    if denied:
        return denied
    page_data = repo.items_for_log_id(log_id)

    return render_template("job_log_item_list.html", page_data=page_data)


@main.route('/job_log_detail', methods=['GET'])
@require_permission('log:read')
def job_log_detail():
    job_log_id = request.args.get('id')
    repo = _job_log_repo()
    jl = repo.get(JobLog, job_log_id)
    if not jl:
        return render_template("job_log_detail.html", jl=None, cif=None, items=[])
    cif = db.session.get(CronInfos, jl.cron_info_id)
    denied = authorize_resource('log:read', cif)
    if denied:
        return denied
    items = repo.items_for_log_id(jl.log_id) if jl.log_id else []
    return render_template("job_log_detail.html", jl=jl, cif=cif, items=items)


@main.route('/job_log_all_list', methods=['GET', 'POST'])
@require_permission('log:read')
def job_log_all_list():
    keywords = request.args.to_dict()

    page_query = PageQuery.from_args(request.args)
    outcome = _parse_log_outcome_param()

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
    outcome_clause = job_log_outcome_clause(outcome)
    if outcome_clause is not None:
        filter_arr.append(outcome_clause)

    page_data = _job_log_repo().paginate_all(page_query, filters=filter_arr)

    if 'page' in keywords:
        del keywords['page']
    keywords['outcome'] = outcome

    return render_template(
        "job_log_all_list.html",
        page_data=page_data,
        keywords=keywords,
        outcome=outcome,
    )


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
@csrf_protect
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
            err, field = add_cron_web(datas, is_dev, CRON_CONFIG)
            if err:
                payload = {'field': field} if field else None
                return web_api_return(code=1, msg=err, data=payload)
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
@csrf_protect
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
        err, field = edit_cron_web(datas, is_dev, CRON_CONFIG, id)
        if err:
            payload = {'field': field} if field else None
            return web_api_return(code=1, msg=err, data=payload)
        return web_api_return(code=0, msg='修改成功！', url='/cron_list')

    return render_template(
        "cron_edit.html",
        cif=cif,
        is_dev=is_dev,
    )


@main.route('/update_status', methods=['POST'])
@require_permission('cron:write')
@csrf_protect
def update_status():
    from app.services.operation_log_service import record_operation

    id = request.values.get('id') or request.args.get('id')
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


@main.route('/cron_run_now', methods=['POST'])
@require_permission('cron:write')
@csrf_protect
def cron_run_now():
    from app.crons import cron_do

    id = request.values.get('id') or request.args.get('id')
    cif = db.session.get(CronInfos, id)
    if not cif:
        return web_api_return(code=1, msg='任务不存在', url='/cron_list')
    denied = authorize_resource('cron:write', cif)
    if denied:
        return denied
    if cif.status == -1:
        return web_api_return(code=1, msg='任务已下线，不能执行')
    if cif.status != 1:
        return web_api_return(code=1, msg='任务未在运行中，不能立即执行')
    if not cif.req_url:
        return web_api_return(code=1, msg='未配置触发 URL，不能执行')
    job_log_id = cron_do(int(id))
    if not job_log_id:
        return web_api_return(code=1, msg='任务正在执行中，请稍后再试')
    return web_api_return(
        code=0,
        msg='执行完成',
        url=url_for('main.job_log_detail', id=job_log_id),
    )


@main.route('/cron_retire', methods=['GET', 'POST'])
@require_permission('cron:retire')
@csrf_protect
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
    from app.services.operation_log_service import (
        format_detail_summary,
        operation_action_label,
        operation_result_label,
    )

    keywords = request.args.to_dict()
    page_query = PageQuery.from_args(request.args)
    role = session.get('role') or ''
    group_ids = session_group_ids()
    task_name = (keywords.get('task_name') or '').strip()
    operator_name = (keywords.get('operator_name') or '').strip()
    action = (keywords.get('action') or '').strip()
    beg_time = (keywords.get('beg_time') or '').strip()
    end_time = (keywords.get('end_time') or '').strip()

    scope_view, scope_group_id, ui_scope_clause = _parse_ui_scope_view(
        role,
        group_ids,
        keywords.get('scope_view'),
        keywords.get('group_id'),
    )

    scope_clause = None
    if not role_bypasses_scope(role):
        scope_clause = build_scope_filter_clause(role, group_ids)

    page_data = _operation_log_repo().paginate_list(
        page_query,
        task_name=task_name or None,
        operator_name=operator_name or None,
        action=action or None,
        beg_time=beg_time or None,
        end_time=end_time or None,
        scope_clause=scope_clause,
        ui_scope_clause=ui_scope_clause,
        bypass_scope=role_bypasses_scope(role),
    )

    cron_by_id = _cron_repo().map_by_ids([
        r.target_id for r in page_data.items
        if r.target_type == 'cron' and r.target_id
    ])

    scope_groups = _scope_groups_for_form()
    group_name_by_id = {g.id: g.name for g in scope_groups}
    if role_bypasses_scope(role):
        try:
            scope_groups = list_resource_groups()
            group_name_by_id = {g.id: g.name for g in scope_groups}
        except Exception:
            pass

    if 'page' in keywords:
        del keywords['page']
    keywords['scope_view'] = scope_view
    if scope_group_id is not None:
        keywords['group_id'] = str(scope_group_id)
    elif 'group_id' in keywords and scope_view != 'group':
        keywords.pop('group_id', None)

    return render_template(
        'operation_log_list.html',
        page_data=page_data,
        keywords=keywords,
        scope_view=scope_view,
        scope_group_id=scope_group_id,
        scope_groups=scope_groups,
        group_name_by_id=group_name_by_id,
        cron_by_id=cron_by_id,
        operation_action_label=operation_action_label,
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
