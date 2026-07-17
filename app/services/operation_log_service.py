# -*- coding:utf-8 -*-
"""业务配置变更审计（OPT-P1-09）。写失败不回滚业务事务。"""
import hashlib
import json
import logging
from dataclasses import dataclass, field

from flask import has_request_context, request, session
from sqlalchemy import delete, func, select

from app import db
from app.rbac.policy import ROLE_PERMISSIONS
from datas.model.operation_log import OperationLog
from datas.utils.times import get_now_time

logger = logging.getLogger(__name__)

ACTION_LABELS = {
    'create_cron': '创建任务',
    'update_cron': '修改任务',
    'toggle_status': '启动/暂停',  # 列表默认；有 detail 时按新旧 status 显示「启动任务」或「暂停任务」
    'retire_cron': '下线任务',
}
CHANNEL_LABELS = {
    'web': '管理端',
    'api': 'API',
    'system': '系统',
}
RESULT_LABELS = {
    'ok': '成功',
    'fail': '失败',
}

# cron_infos.status：0=已暂停，1=运行中，-1=已下线
STATUS_RUN_LABELS = {
    0: '已暂停',
    1: '运行中',
    -1: '已下线',
}

CRON_SNAPSHOT_FIELDS = (
    'task_name',
    'task_keyword',
    'run_date',
    'day_of_week',
    'day',
    'hour',
    'minute',
    'second',
    'req_url',
    'req_method',
    'req_body',
    'status',
    'scope_type',
    'group_id',
)


@dataclass
class OperatorContext:
    operator_type: str
    operator_id: str = ''
    operator_name: str = ''
    roles: list = field(default_factory=list)
    permissions: list = field(default_factory=list)


def _parse_detail(detail_json):
    try:
        detail = json.loads(detail_json) if detail_json else {}
    except (TypeError, ValueError):
        return {}
    return detail if isinstance(detail, dict) else {}


def _status_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def toggle_status_verb(detail):
    """根据 status 新旧值返回「启动」或「暂停」；无法判断时返回空串。"""
    if not isinstance(detail, dict):
        return ''
    change = detail.get('status') or {}
    if not isinstance(change, dict):
        return ''
    old_s = _status_int(change.get('old'))
    new_s = _status_int(change.get('new'))
    if old_s == 0 and new_s == 1:
        return '启动'
    if old_s == 1 and new_s == 0:
        return '暂停'
    return ''


def operation_action_label(action, detail_json=None):
    """动作中文名。toggle_status 有详情时区分「启动任务」「暂停任务」。"""
    action = action or ''
    if action == 'toggle_status' and detail_json is not None:
        verb = toggle_status_verb(_parse_detail(detail_json))
        if verb:
            return '%s任务' % verb
    return ACTION_LABELS.get(action, action)


def operation_channel_label(channel):
    channel = channel or ''
    return CHANNEL_LABELS.get(channel, channel)


def operation_result_label(result):
    result = result or ''
    return RESULT_LABELS.get(result, result)


def snapshot_cron(cif):
    if cif is None:
        return {}
    out = {}
    for key in CRON_SNAPSHOT_FIELDS:
        out[key] = getattr(cif, key, None)
    return out


def build_cron_diff(before, after):
    """before/after 为 dict；仅输出有变化的字段 {field: {old, new}}。"""
    before = before or {}
    after = after or {}
    diff = {}
    keys = set(before) | set(after)
    for key in keys:
        old = before.get(key)
        new = after.get(key)
        if old != new:
            diff[key] = {'old': old, 'new': new}
    return diff


def _client_ip():
    if not has_request_context():
        return ''
    forwarded = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    return forwarded or (request.remote_addr or '')


def _detect_channel():
    if not has_request_context():
        return 'system'
    path = request.path or ''
    if path.startswith('/api'):
        return 'api'
    return 'web'


def resolve_operator_from_request():
    """Web：Session 用户；API：api_client；无请求上下文：system。"""
    if not has_request_context():
        return OperatorContext(
            operator_type='system',
            operator_name='系统',
            roles=['system'],
            permissions=['*'],
        )
    channel = _detect_channel()
    if channel == 'api':
        token = request.values.get('access_token') or ''
        oid = ''
        if token:
            oid = hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]
        return OperatorContext(
            operator_type='api_client',
            operator_id=oid,
            operator_name='API集成',
            roles=['api_scheduler'],
            permissions=sorted(ROLE_PERMISSIONS.get('operator', set()) | {'cron:write'}),
        )
    uid = session.get('user_id')
    username = session.get('username') or ''
    role = session.get('role') or 'admin'
    perms = sorted(ROLE_PERMISSIONS.get(role, set()))
    return OperatorContext(
        operator_type='user',
        operator_id=str(uid) if uid is not None else '',
        operator_name=username or '用户',
        roles=[role] if role else [],
        permissions=perms,
    )


def record_operation(
    *,
    action,
    channel=None,
    operator=None,
    target_type='cron',
    target_id=None,
    task_name='',
    detail=None,
    result='ok',
    error_msg='',
    client_ip=None,
):
    """业务 commit 成功后调用；异常仅记日志。"""
    try:
        if operator is None:
            operator = resolve_operator_from_request()
        if channel is None:
            channel = _detect_channel()
        if client_ip is None:
            client_ip = _client_ip()
        row = OperationLog(
            create_time=get_now_time(),
            action=action or '',
            channel=channel or '',
            operator_type=operator.operator_type or '',
            operator_id=operator.operator_id or '',
            operator_name=operator.operator_name or '',
            operator_roles_json=json.dumps(operator.roles or [], ensure_ascii=False),
            operator_permissions_json=json.dumps(
                operator.permissions or [], ensure_ascii=False
            ),
            client_ip=client_ip or '',
            target_type=target_type or 'cron',
            target_id=target_id,
            task_name=task_name or '',
            detail_json=json.dumps(detail or {}, ensure_ascii=False),
            result=result or 'ok',
            error_msg=(error_msg or '')[:255],
        )
        db.session.add(row)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception('operation_log write failed action=%s', action)


def trim_operation_logs(keep_count):
    """全局保留最近 keep_count 条（按 id），删除更旧的。"""
    keep_count = int(keep_count)
    if keep_count <= 0:
        return 0
    total = db.session.scalar(
        select(func.count()).select_from(OperationLog)
    ) or 0
    excess = total - keep_count
    if excess <= 0:
        return 0
    ids = list(
        db.session.scalars(
            select(OperationLog.id)
            .order_by(OperationLog.id.asc())
            .limit(excess)
        )
    )
    if ids:
        db.session.execute(delete(OperationLog).where(OperationLog.id.in_(ids)))
    return len(ids)


def format_detail_summary(action, detail_json):
    """列表「详情」短文案。"""
    if detail_json in (None, ''):
        detail = {}
    else:
        try:
            parsed = json.loads(detail_json) if not isinstance(detail_json, dict) else detail_json
        except (TypeError, ValueError):
            return detail_json or ''
        if not isinstance(parsed, dict):
            return str(parsed)
        detail = parsed
    if action == 'create_cron':
        parts = []
        for key in ('hour', 'minute', 'req_url'):
            if key in detail and detail[key] not in (None, ''):
                parts.append('%s=%s' % (key, detail[key]))
        return '、'.join(parts) if parts else '新建'
    if action == 'update_cron':
        parts = []
        for key, change in detail.items():
            if isinstance(change, dict) and 'old' in change and 'new' in change:
                parts.append('%s %s→%s' % (key, change['old'], change['new']))
        return '、'.join(parts) if parts else '修改'
    if action == 'toggle_status':
        change = detail.get('status') or {}
        if isinstance(change, dict):
            old_s = _status_int(change.get('old'))
            new_s = _status_int(change.get('new'))
            old_label = STATUS_RUN_LABELS.get(old_s, change.get('old'))
            new_label = STATUS_RUN_LABELS.get(new_s, change.get('new'))
            verb = toggle_status_verb(detail)
            if verb:
                return '%s：%s → %s' % (verb, old_label, new_label)
            return '%s → %s' % (old_label, new_label)
        return ''
    if action == 'retire_cron':
        reason = detail.get('reason') or ''
        return ('下线：%s' % reason) if reason else '下线'
    if detail:
        return json.dumps(detail, ensure_ascii=False)[:120]
    return ''
