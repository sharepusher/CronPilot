# -*- coding:utf-8 -*-
"""Resource Scope：可见范围（OPT-P2-12）。与 RBAC Permission 解耦。"""
from sqlalchemy import or_, select

from app import db
from datas.model.cron_infos import CronInfos
from datas.model.user_group import UserGroup

from .policy import role_bypasses_scope

SCOPE_GLOBAL = 'GLOBAL'
SCOPE_GROUP = 'GROUP'
VALID_SCOPE_TYPES = frozenset({SCOPE_GLOBAL, SCOPE_GROUP})


def get_user_group_ids(user_id):
    """返回用户所属业务组 id 列表；user_id 无效时返回 []."""
    if user_id is None:
        return []
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return []
    rows = db.session.scalars(
        select(UserGroup.group_id).where(UserGroup.user_id == user_id)
    ).all()
    return [int(g) for g in rows if g is not None]


def normalize_scope_fields(scope_type, group_id):
    """校验并规范落库字段。成功返回 (None, scope_type, group_id)；失败 (err, None, None)。"""
    scope_type = (scope_type or SCOPE_GLOBAL).strip().upper()
    if scope_type not in VALID_SCOPE_TYPES:
        return '作用域无效，可选 GLOBAL / GROUP', None, None
    if scope_type == SCOPE_GLOBAL:
        return None, SCOPE_GLOBAL, None
    if group_id is None or group_id == '':
        return '业务组作用域须选择业务组', None, None
    try:
        group_id = int(group_id)
    except (TypeError, ValueError):
        return '业务组无效', None, None
    if group_id <= 0:
        return '业务组无效', None, None
    return None, SCOPE_GROUP, group_id


def user_can_assign_group(role, group_ids, group_id):
    """非 admin 仅能把资源写入自身所属组；admin 可写任意组。"""
    if role_bypasses_scope(role):
        return True
    if group_id is None:
        return True
    return int(group_id) in set(int(g) for g in (group_ids or []))


def has_scope(role, group_ids, resource):
    """resource 须暴露 scope_type / group_id（如 CronInfos）。"""
    if resource is None:
        return False
    if role_bypasses_scope(role):
        return True
    scope_type = (getattr(resource, 'scope_type', None) or SCOPE_GLOBAL).upper()
    if scope_type == SCOPE_GLOBAL:
        return True
    if scope_type != SCOPE_GROUP:
        return False
    gid = getattr(resource, 'group_id', None)
    if gid is None:
        return False
    allowed = set(int(g) for g in (group_ids or []))
    return int(gid) in allowed


def build_scope_filter_clause(role, group_ids, model=None):
    """返回 SQLAlchemy 条件；admin 返回 None（调用方不追加过滤）。"""
    model = model or CronInfos
    if role_bypasses_scope(role):
        return None
    ids = [int(g) for g in (group_ids or [])]
    if not ids:
        return model.scope_type == SCOPE_GLOBAL
    return or_(
        model.scope_type == SCOPE_GLOBAL,
        model.group_id.in_(ids),
    )
