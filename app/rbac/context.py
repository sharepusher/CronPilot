from flask import session

from .services import get_role_permission_set


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
    """按 Session 角色裁剪模板；分权始终启用。"""
    role = session.get('role') or ''
    user_perms = get_role_permission_set(role)

    def _has_perm(permission):
        return permission in user_perms

    return _has_perm


def get_current_group_ids():
    gids = session.get('group_ids')
    if not isinstance(gids, list):
        return []
    return list(gids)
