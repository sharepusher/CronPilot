# -*- coding:utf-8 -*-
"""Resource Scope：可见范围（OPT-P2-12）。与 RBAC Permission 解耦。"""
from sqlalchemy import or_, select

from app import db
from datas.model.cron_infos import CronInfos
from datas.model.task_group import TaskGroup
from datas.model.user_group import UserGroup

from .policy import role_bypasses_scope, user_bypasses_scope

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


def normalize_scope_fields(scope_type, group_id=None):
    """校验并规范落库字段。

    成功返回 (None, scope_type, group_id|None)；失败 (err, None, None)。
    业务规则：一个任务属于恰好一个业务组（GROUP），或全局公开（GLOBAL）。
    """
    scope_type = (scope_type or SCOPE_GLOBAL).strip().upper()
    if scope_type not in VALID_SCOPE_TYPES:
        return '作用域无效，可选 GLOBAL / GROUP', None, None
    if scope_type == SCOPE_GLOBAL:
        return None, SCOPE_GLOBAL, None
    if not group_id:
        return '业务组作用域须选择业务组', None, None
    try:
        group_id = int(group_id)
    except (TypeError, ValueError):
        return '业务组无效', None, None
    if group_id <= 0:
        return '业务组无效', None, None
    return None, SCOPE_GROUP, group_id


def user_can_assign_group(role, group_ids, group_id, username=None):
    """非 bypass 用户仅能把资源写入自身所属组；bypass 用户可写任意组。"""
    if user_bypasses_scope(role, username=username, group_ids=group_ids):
        return True
    if group_id is None:
        return True
    return int(group_id) in set(int(g) for g in (group_ids or []))


def get_task_group_id(task_id):
    """返回任务关联的业务组 id（来自 task_groups 表）；无则返回 None。"""
    if task_id is None:
        return None
    row = db.session.scalars(
        select(TaskGroup.group_id).where(TaskGroup.task_id == int(task_id))
    ).first()
    return int(row) if row is not None else None


def get_task_group_ids(task_id):
    """兼容：返回任务关联的业务组 id 列表。"""
    gid = get_task_group_id(task_id)
    return [gid] if gid is not None else []


def has_scope(role, group_ids, resource, username=None):
    """resource 须暴露 scope_type（如 CronInfos）。组关系通过 task_groups 查询。"""
    if resource is None:
        return False
    if user_bypasses_scope(role, username=username, group_ids=group_ids):
        return True
    scope_type = (getattr(resource, 'scope_type', None) or SCOPE_GLOBAL).upper()
    if scope_type == SCOPE_GLOBAL:
        return True
    if scope_type != SCOPE_GROUP:
        return False
    task_gids = get_task_group_ids(getattr(resource, 'id', None))
    if not task_gids:
        return False
    allowed = set(int(g) for g in (group_ids or []))
    return bool(allowed & set(task_gids))


def build_scope_filter_clause(role, group_ids, model=None, username=None):
    """返回 SQLAlchemy 条件；bypass 用户返回 None（调用方不追加过滤）。

    OPT-P1-11：GROUP 可见性通过 task_groups 子查询实现，不再依赖 cron_infos.group_id。
    """
    model = model or CronInfos
    if user_bypasses_scope(role, username=username, group_ids=group_ids):
        return None
    ids = [int(g) for g in (group_ids or [])]
    if not ids:
        return model.scope_type == SCOPE_GLOBAL
    visible_task_ids = select(TaskGroup.task_id).where(
        TaskGroup.group_id.in_(ids)
    ).correlate(None).scalar_subquery()
    return or_(
        model.scope_type == SCOPE_GLOBAL,
        model.id.in_(visible_task_ids),
    )
