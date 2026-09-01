#!/usr/bin/python3
# -*- coding:utf-8 -*-
from flask import current_app, request
from sqlalchemy import func, select

from app import db
from app.decorated import api_deal_return, api_err_return
from app.services.cron_service import upsert_cron_by_task_name
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.model.job_log_items import JobLogItems
from datas.utils.json import api_return

from ..crons import cron_do
from . import api
from .schemas import AddLogIn, CronRetireIn, CronStatusIn, CronUpsertIn


def _parse_limit_offset(limit_default=20, limit_max=100):
    """解析通用分页参数（limit/offset）。"""
    try:
        limit = int((request.args.get('limit') or '').strip() or str(limit_default))
    except (TypeError, ValueError):
        return None, None, 'limit 参数无效'
    try:
        offset = int((request.args.get('offset') or '').strip() or '0')
    except (TypeError, ValueError):
        return None, None, 'offset 参数无效'
    if limit <= 0 or limit > limit_max:
        return None, None, 'limit 必须在 1-%s 之间' % limit_max
    if offset < 0:
        return None, None, 'offset 必须大于等于 0'
    return limit, offset, ''


def _query_scope_context():
    """提取当前 API 请求的角色、组与用户名（用于只读查询接口）。

    返回 (role, group_ids, username)。
    """
    from app.rbac.policy import user_bypasses_scope

    scope = getattr(request, '_api_scope', None) or {'role': 'admin'}
    if scope.get('role') == 'admin':
        return 'admin', [], 'admin'
    user_role = scope.get('user_role', '')
    group_ids = scope.get('group_ids', [])
    username = scope.get('username', '')
    return user_role, group_ids, username


# ---------------------------------------------------------------------------
# S6 — /api/auth/token（用户名/密码 → 签发 API Token）
# ---------------------------------------------------------------------------

@api.post('/auth/token')
@api.doc(
    summary='获取/续签 API Token',
    description=(
        '用 HTTP Basic Auth（`Authorization: Basic base64(username:password)`）或 '
        'form 参数 `username` + `password` 认证，签发有效期 30 天的 API Token。\n\n'
        '**Token 过期后需重新调用此接口获取新 Token。**\n\n'
        '返回 `{errcode:0, result: {token, expires_at}}`。'
    ),
    tags=['认证'],
)
def api_auth_token():
    import base64

    from app.rbac.services import issue_user_api_token
    from datas.model.rbac_user import RbacUser

    username = request.values.get('username', '')
    password = request.values.get('password', '')

    if not username:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Basic '):
            try:
                decoded = base64.b64decode(auth_header[6:].strip()).decode('utf-8')
                if ':' in decoded:
                    username, password = decoded.split(':', 1)
            except Exception:
                pass

    if not username or not password:
        return api_return(errcode=1, errmsg='缺少 username 或 password'), 401

    user = db.session.scalars(
        select(RbacUser).where(RbacUser.username == username)
    ).first()
    if not user or not user.check_password(password):
        from . import _write_api_deny_audit
        _write_api_deny_audit()
        return api_return(errcode=1, errmsg='用户名或密码错误'), 401
    if not user.is_active:
        return api_return(errcode=1, errmsg='用户已停用'), 401

    result = issue_user_api_token(user.id)
    if not result['ok']:
        return api_return(errcode=1, errmsg=result['msg']), 500

    return api_return(errcode=0, errmsg='ok', data={
        'token': result['token'],
        'expires_at': result['expires_at'],
    })


# ---------------------------------------------------------------------------
# Batch 4.1 — /api/test（无输入，验证迁移机制）
# ---------------------------------------------------------------------------

@api.get('/test')
@api.doc(summary='接口连通性测试', tags=['系统'])
def test():
    return api_return(errcode=0, errmsg='test')


# ---------------------------------------------------------------------------
# 查询接口（只读语义）
# ---------------------------------------------------------------------------

@api.get('/cron/query')
@api.doc(
    summary='查询任务（只读）',
    description=(
        '按权限与 Scope 过滤查询任务。\n\n'
        '支持参数：`task_name`（精确）、`keyword`（模糊）、`status`（-1/0/1）、`limit`、`offset`。'
    ),
    tags=['查询'],
)
def cron_query():
    from app.rbac.scope import build_scope_filter_clause

    limit, offset, err = _parse_limit_offset()
    if err:
        return api_return(errcode=1, errmsg=err)

    task_name = (request.args.get('task_name') or '').strip()
    keyword = (request.args.get('keyword') or '').strip()
    status_raw = (request.args.get('status') or '').strip()
    req_method = (request.args.get('req_method') or '').strip().upper()
    updated_from = (request.args.get('updated_from') or '').strip()
    updated_to = (request.args.get('updated_to') or '').strip()

    filters = []
    role, group_ids, username = _query_scope_context()
    scope_clause = build_scope_filter_clause(role, group_ids, CronInfos, username=username)
    if scope_clause is not None:
        filters.append(scope_clause)
    if task_name:
        filters.append(CronInfos.task_name == task_name)
    if keyword:
        filters.append(CronInfos.task_name.like('%%%s%%' % keyword))
    if status_raw != '':
        try:
            status = int(status_raw)
        except (TypeError, ValueError):
            return api_return(errcode=1, errmsg='status 参数无效')
        if status not in (-1, 0, 1):
            return api_return(errcode=1, errmsg='status 参数无效')
        filters.append(CronInfos.status == status)
    scope_type = (request.args.get('scope_type') or '').strip().upper()
    if scope_type:
        if scope_type not in ('GLOBAL', 'GROUP'):
            return api_return(errcode=1, errmsg='scope_type 参数无效')
        filters.append(CronInfos.scope_type == scope_type)
    group_id_raw = (request.args.get('group_id') or '').strip()
    if group_id_raw:
        try:
            group_id = int(group_id_raw)
        except (TypeError, ValueError):
            return api_return(errcode=1, errmsg='group_id 参数无效')
        if group_id <= 0:
            return api_return(errcode=1, errmsg='group_id 参数无效')
        from datas.model.task_group import TaskGroup
        task_ids_in_group = select(TaskGroup.task_id).where(
            TaskGroup.group_id == group_id
        ).correlate(None).scalar_subquery()
        filters.append(CronInfos.id.in_(task_ids_in_group))
    if req_method:
        if req_method not in ('GET', 'POST'):
            return api_return(errcode=1, errmsg='req_method 参数无效')
        filters.append(CronInfos.req_method == req_method)
    if updated_from:
        filters.append(CronInfos.updated_at >= updated_from)
    if updated_to:
        filters.append(CronInfos.updated_at <= updated_to)

    total = db.session.scalar(
        select(func.count()).select_from(CronInfos).where(*filters)
    ) or 0

    rows = db.session.scalars(
        select(CronInfos)
        .where(*filters)
        .order_by(CronInfos.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    from app.rbac.scope import get_task_group_id
    items = [{
        'id': row.id,
        'task_name': row.task_name,
        'status': row.status,
        'scope_type': row.scope_type,
        'group_id': get_task_group_id(row.id),
        'req_method': row.req_method or 'GET',
        'req_url': row.req_url or '',
        'updated_at': row.updated_at or '',
    } for row in rows]
    return api_return(errcode=0, errmsg='ok', data={
        'items': items,
        'count': len(items),
        'total': int(total),
        'limit': limit,
        'offset': offset,
        'has_more': (offset + len(items)) < int(total),
    })


@api.get('/cron/logs')
@api.doc(
    summary='查询任务执行日志（只读）',
    description=(
        '按任务名称查询执行日志（倒序）。\n\n'
        '需要参数：`task_name`；可选参数：`limit`、`offset`。'
    ),
    tags=['查询'],
)
def cron_logs():
    from . import check_api_scope

    task_name = (request.args.get('task_name') or '').strip()
    if not task_name:
        return api_return(errcode=1, errmsg='task_name 不能为空')

    limit, offset, err = _parse_limit_offset()
    if err:
        return api_return(errcode=1, errmsg=err)

    cron = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == task_name)
    ).first()
    if not cron:
        return api_return(errcode=1, errmsg='任务不存在')
    denied = check_api_scope(cron)
    if denied is not None:
        return denied
    status_filter = (request.args.get('status') or '').strip().lower()
    http_status_raw = (request.args.get('http_status') or '').strip()
    beg_time = (request.args.get('beg_time') or '').strip()
    end_time = (request.args.get('end_time') or '').strip()
    allowed_status = {'success', 'fail', 'timeout', 'error', 'pending', 'running'}
    if status_filter and status_filter not in allowed_status:
        return api_return(errcode=1, errmsg='status 参数无效')

    log_filters = [JobLog.cron_info_id == cron.id]
    if status_filter:
        log_filters.append(JobLog.status == status_filter)
    if http_status_raw:
        try:
            http_status = int(http_status_raw)
        except (TypeError, ValueError):
            return api_return(errcode=1, errmsg='http_status 参数无效')
        log_filters.append(JobLog.http_status == http_status)
    from datas.utils.times import hms_to_str, str_to_hms
    if beg_time:
        log_filters.append(JobLog.create_time >= str_to_hms(beg_time + ' 00:00:00'))
    if end_time:
        log_filters.append(JobLog.create_time <= str_to_hms(end_time + ' 23:59:59'))
    total = db.session.scalar(
        select(func.count()).select_from(JobLog).where(*log_filters)
    ) or 0
    rows = db.session.scalars(
        select(JobLog)
        .where(*log_filters)
        .order_by(JobLog.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    items = [{
        'id': row.id,
        'trace_id': row.trace_id or '',
        'status': row.status or '',
        'http_status': row.http_status,
        'fail_reason': row.fail_reason or '',
        'create_time': hms_to_str(row.create_time) or '',
        'take_time': row.take_time or '',
        'started_at': row.started_at or '',
        'finished_at': row.finished_at or '',
        'timeout_sec': row.timeout_sec,
        'content_preview': (row.content or '')[:120],
    } for row in rows]
    return api_return(errcode=0, errmsg='ok', data={
        'task_name': cron.task_name,
        'items': items,
        'count': len(items),
        'total': int(total),
        'limit': limit,
        'offset': offset,
        'has_more': (offset + len(items)) < int(total),
    })


@api.get('/cron/detail')
@api.doc(
    summary='查询单个任务详情（只读）',
    description='按 `task_name`（或 `id`）查询单个任务详情，受 Scope 控制。',
    tags=['查询'],
)
def cron_detail():
    from . import check_api_scope

    task_name = (request.args.get('task_name') or '').strip()
    id_raw = (request.args.get('id') or '').strip()
    if not task_name and not id_raw:
        return api_return(errcode=1, errmsg='task_name 或 id 至少提供一个')
    cron = None
    if task_name:
        cron = db.session.scalars(
            select(CronInfos).where(CronInfos.task_name == task_name)
        ).first()
    elif id_raw:
        try:
            cron = db.session.get(CronInfos, int(id_raw))
        except (TypeError, ValueError):
            return api_return(errcode=1, errmsg='id 参数无效')
    if not cron:
        return api_return(errcode=1, errmsg='任务不存在')
    denied = check_api_scope(cron)
    if denied is not None:
        return denied
    from app.rbac.scope import get_task_group_id
    return api_return(errcode=0, errmsg='ok', data={
        'id': cron.id,
        'task_name': cron.task_name,
        'task_keyword': cron.task_keyword or '',
        'run_date': cron.run_date or '',
        'day_of_week': cron.day_of_week or '',
        'day': cron.day or '',
        'hour': cron.hour or '',
        'minute': cron.minute or '',
        'second': cron.second or '',
        'req_url': cron.req_url or '',
        'req_method': cron.req_method or 'GET',
        'req_body': cron.req_body or '',
        'status': cron.status,
        'scope_type': cron.scope_type,
        'group_id': get_task_group_id(cron.id),
        'created_at': cron.created_at or '',
        'updated_at': cron.updated_at or '',
        'retired_at': cron.retired_at or '',
        'retire_reason': cron.retire_reason or '',
        'timeout_sec': cron.timeout_sec,
    })


@api.get('/cron/log/detail')
@api.doc(
    summary='查询单条执行日志详情（只读）',
    description='按 `id`（或 `trace_id`）查询单条执行日志详情，受任务 Scope 控制。',
    tags=['查询'],
)
def cron_log_detail():
    from . import check_api_scope

    id_raw = (request.args.get('id') or '').strip()
    trace_id_param = (request.args.get('trace_id') or '').strip()
    if not id_raw and not trace_id_param:
        return api_return(errcode=1, errmsg='id 或 trace_id 至少提供一个')

    log = None
    if id_raw:
        try:
            log = db.session.get(JobLog, int(id_raw))
        except (TypeError, ValueError):
            return api_return(errcode=1, errmsg='id 参数无效')
    elif trace_id_param:
        log = db.session.scalars(
            select(JobLog).where(JobLog.trace_id == trace_id_param)
        ).first()
    if not log:
        return api_return(errcode=1, errmsg='任务不存在')

    cron = db.session.get(CronInfos, log.cron_info_id)
    if not cron:
        return api_return(errcode=1, errmsg='任务不存在')
    denied = check_api_scope(cron)
    if denied is not None:
        return denied

    from datas.utils.times import hms_to_str
    return api_return(errcode=0, errmsg='ok', data={
        'id': log.id,
        'trace_id': log.trace_id or '',
        'task_name': cron.task_name,
        'cron_info_id': log.cron_info_id,
        'status': log.status or '',
        'http_status': log.http_status,
        'fail_reason': log.fail_reason or '',
        'content': log.content or '',
        'create_time': hms_to_str(log.create_time) or '',
        'take_time': log.take_time or '',
        'started_at': log.started_at or '',
        'finished_at': log.finished_at or '',
        'timeout_sec': log.timeout_sec,
    })


# ---------------------------------------------------------------------------
# Batch 4.2 — /api/cron/add_log（业务方回传执行进度）
# ---------------------------------------------------------------------------

@api.post('/cron/add_log')
@api.doc(
    summary='业务方回传执行进度',
    description=(
        '业务方在处理 CronPilot 定时触发时，可调用此接口写入阶段性进度记录。\n\n'
        '**认证**：conf.ini 配置 `api_access_token` 后，需通过 '
        '`Authorization: Bearer <token>` Header 或 `access_token` query/form 参数传递。'
    ),
    tags=['执行日志'],
)
@api.input(AddLogIn, location='form', arg_name='form_data')
def cron_add_log(form_data):
    cronpilot_trace_id = form_data.get('cronpilot_trace_id')
    content = form_data.get('content')

    jl = db.session.scalars(
        select(JobLog).where(JobLog.trace_id == cronpilot_trace_id)
    ).first()
    if not jl:
        return api_return(errcode=1, errmsg='cronpilot_trace_id 不存在')

    jli = JobLogItems(trace_id=cronpilot_trace_id, content=content)
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

    from . import check_api_scope

    task_name = form_data.get('task_name')
    reason = form_data.get('reason')

    ci = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == task_name)
    ).first()
    if not ci:
        return api_return(errcode=1, errmsg='任务不存在')
    denied = check_api_scope(ci)
    if denied is not None:
        return denied

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
    from . import check_api_scope

    task_name = form_data.get('task_name')
    status = form_data.get('status')

    ci = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == task_name)
    ).first()
    if not ci:
        return api_return(errcode=1, errmsg='任务不存在')
    denied = check_api_scope(ci)
    if denied is not None:
        return denied

    from app.services.cron_service import toggle_status

    ok, msg, _old, _new = toggle_status(ci.id, target_status=status)
    return api_return(errcode=0 if ok else 1, errmsg=msg)


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
    from . import check_api_scope

    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    is_dev = int(CRON_CONFIG.get('is_dev'))

    task_name = form_data.get('task_name')
    if task_name:
        existing = db.session.scalars(
            select(CronInfos).where(CronInfos.task_name == task_name)
        ).first()
        if existing:
            denied = check_api_scope(existing)
            if denied is not None:
                return denied

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
    from . import check_api_scope

    CRON_CONFIG = current_app.config.get('CRON_CONFIG')
    is_dev = int(CRON_CONFIG.get('is_dev'))
    datas = request.values.to_dict()
    task_name = datas.get('task_name')

    if not task_name:
        return api_err_return(msg='任务名称不能为空')

    existing = db.session.scalars(
        select(CronInfos).where(CronInfos.task_name == task_name)
    ).first()
    if existing:
        denied = check_api_scope(existing)
        if denied is not None:
            return denied

    err, _cif = upsert_cron_by_task_name(datas, is_dev, CRON_CONFIG)
    if err:
        return api_err_return(msg=err)

    return 'ok'
