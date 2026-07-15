from flask import g, session

from .policy import is_seed_admin_username, role_bypasses_scope
from .services import get_role_permission_set

ROLE_DISPLAY = {
    'admin': '业务管理员',
    'operator': 'operator',
    'viewer': 'viewer',
}

SEED_ADMIN_DISPLAY = '系统管理员'


def get_current_user():
    if 'is_login' not in session:
        return None
    return {
        'username': session.get('username', ''),
        'role': session.get('role', ''),
        'user_id': session.get('user_id'),
        'group_ids': list(session.get('group_ids') or []),
    }


def make_has_perm():
    """按 Session 角色（及种子账号裁剪）裁剪模板；分权始终启用。"""
    role = session.get('role') or ''
    username = session.get('username') or ''
    user_perms = get_role_permission_set(role, username=username)

    def _has_perm(permission):
        return permission in user_perms

    return _has_perm


def get_current_group_ids():
    gids = session.get('group_ids')
    if not isinstance(gids, list):
        return []
    return list(gids)


def get_current_user_groups():
    """
    解析 session['group_ids'] 为 {id, name} 列表，供顶栏展示。
    admin（绕过 Scope）返回 []，模板不展示 Scope 标签。
    与授权同源：组变更须重新登录后 session 才更新。
    """
    if hasattr(g, '_current_user_groups'):
        return g._current_user_groups

    if 'is_login' not in session:
        g._current_user_groups = []
        return []

    role = session.get('role') or ''
    if role_bypasses_scope(role):
        g._current_user_groups = []
        return []

    raw_ids = session.get('group_ids') or []
    ids = []
    for gid in raw_ids:
        try:
            ids.append(int(gid))
        except (TypeError, ValueError):
            continue
    if not ids:
        g._current_user_groups = []
        return []

    from sqlalchemy import select

    from app import db
    from datas.model.resource_group import ResourceGroup

    rows = db.session.scalars(
        select(ResourceGroup).where(ResourceGroup.id.in_(ids))
    ).all()
    by_id = {int(r.id): r.name for r in rows}
    result = [{'id': gid, 'name': by_id.get(gid, '组#%s' % gid)} for gid in ids]
    g._current_user_groups = result
    return result


def role_display_name(role, username=None):
    """展示名：种子 admin → 系统管理员；其它 admin → 业务管理员。"""
    if (role or '') == 'admin' and is_seed_admin_username(username):
        return SEED_ADMIN_DISPLAY
    return ROLE_DISPLAY.get(role or '', role or '')


def role_badge_class(role, username=None):
    """顶栏角色标签样式 class 后缀（非灰色语义色）。"""
    if (role or '') == 'admin' and is_seed_admin_username(username):
        return 'seed'
    if role in ('admin', 'operator', 'viewer'):
        return role
    return 'default'
